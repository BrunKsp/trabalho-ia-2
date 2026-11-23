"""
Parser de documentos financeiros agrícolas.
Suporta PDF, CSV e Excel. Usa LLM para extrair lançamentos de PDFs.
"""
import sqlite3, os, json, re
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
import pandas as pd
from pypdf import PdfReader

from .config import DB_PATH

CATEGORIAS_VALIDAS = [
    "Sementes", "Fertilizantes", "Defensivos", "Diesel e operacoes",
    "Mao de obra", "Arrendamento", "Assistencia tecnica",
    "Seguro e juros", "Frete e armazenagem",
]


def extrair_lancamentos_pdf(filepath: str) -> list[dict]:
    """Extrai lançamentos financeiros de um PDF usando LLM."""
    reader = PdfReader(filepath)
    texto = "\n".join(page.extract_text() or "" for page in reader.pages[:10])
    if len(texto.strip()) < 50:
        return []

    cats = ", ".join(CATEGORIAS_VALIDAS)
    prompt = f"""Analise este documento financeiro agrícola e extraia TODOS os lançamentos de despesas encontrados.

Para cada lançamento retorne um objeto JSON com:
- "data": string YYYY-MM-DD
- "categoria": uma de: {cats}
- "fornecedor": nome do fornecedor
- "valor": número float (somente o valor, sem R$)
- "cultura": "soja", "milho" ou "trigo"
- "safra": formato "YYYY/YY" (ex: "2024/25")

Retorne APENAS um array JSON válido. Se não houver lançamentos claros, retorne [].

Documento:
{texto[:4000]}"""

    # Mesmo mecanismo do agente: troca de modelo em 429/erro e começa pelo último
    # que funcionou. Erros de modelo/chave sobem para a interface mostrar ao usuário
    # (antes eram engolidos e apareciam como "nenhum lançamento encontrado").
    from .agente import _create_with_fallback
    resp = _create_with_fallback([{"role": "user", "content": prompt}], usar_ferramentas=False)
    return _parse_json_lancamentos(resp.choices[0].message.content or "")


def _parse_json_lancamentos(content: str) -> list[dict]:
    """Extrai o array JSON da resposta do modelo (tolera ```json ... ``` e texto em volta)."""
    match = re.search(r"\[.*\]", content, re.DOTALL)  # guloso: pega o array inteiro, mesmo com objetos
    if not match:
        return []
    try:
        dados = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    return [d for d in dados if isinstance(d, dict) and "valor" in d]


def extrair_lancamentos_csv(filepath: str) -> list[dict]:
    df = pd.read_csv(filepath, encoding="utf-8", sep=None, engine="python")
    return _mapear_dataframe(df)


def extrair_lancamentos_excel(filepath: str) -> list[dict]:
    df = pd.read_excel(filepath)
    return _mapear_dataframe(df)


def _mapear_dataframe(df: pd.DataFrame) -> list[dict]:
    df.columns = [str(c).lower().strip() for c in df.columns]
    col_map = {
        "data":       ["data", "date", "dt", "data_lancamento", "data lancamento"],
        "valor":      ["valor", "value", "total", "preco", "price", "montante", "vl_total"],
        "categoria":  ["categoria", "category", "tipo", "type", "descricao", "description"],
        "fornecedor": ["fornecedor", "supplier", "empresa", "company", "fornec"],
        "cultura":    ["cultura", "culture", "produto", "crop"],
        "safra":      ["safra", "harvest", "temporada", "ano_safra"],
    }
    mapped = {}
    for field, candidates in col_map.items():
        for col in candidates:
            if col in df.columns:
                mapped[field] = col
                break

    if "valor" not in mapped or "data" not in mapped:
        return []

    lancamentos = []
    for _, row in df.iterrows():
        try:
            lancamentos.append({
                "data":       str(row[mapped["data"]]),
                "valor":      float(str(row[mapped["valor"]]).replace(",", ".").replace("R$", "").strip()),
                "categoria":  str(row.get(mapped.get("categoria", ""), "Outros")),
                "fornecedor": str(row.get(mapped.get("fornecedor", ""), "Não informado")),
                "cultura":    str(row.get(mapped.get("cultura", ""), "soja")).lower(),
                "safra":      str(row.get(mapped.get("safra", ""), "2024/25")),
            })
        except Exception:
            continue
    return lancamentos


def importar_lancamentos(lancamentos: list[dict], fazenda_id: int) -> int:
    """Importa lançamentos para o banco SQLite. Retorna quantidade importada."""
    if not lancamentos:
        return 0
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    max_id = cur.execute("SELECT COALESCE(MAX(id), 0) FROM lancamentos").fetchone()[0]
    importados = 0
    for i, l in enumerate(lancamentos, 1):
        try:
            cur.execute("""
                INSERT INTO lancamentos
                    (id, fazenda_id, safra, cultura, data, categoria, fornecedor, valor, mensagem_whatsapp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                max_id + i,
                fazenda_id,
                l.get("safra", "2024/25"),
                l.get("cultura", "soja").lower(),
                l.get("data", "2024-01-01"),
                l.get("categoria", "Outros"),
                l.get("fornecedor", "Não informado"),
                float(l.get("valor", 0)),
                "importado via upload",
            ))
            importados += 1
        except Exception:
            continue
    con.commit()
    con.close()
    return importados
