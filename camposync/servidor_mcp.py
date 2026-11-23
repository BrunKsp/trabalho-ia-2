"""
Servidor FastMCP - Consultor da Safra
Ferramentas que o agente usa para consultar os dados financeiros do produtor.

É a ÚNICA fonte das ferramentas: o agente (camposync/agente.py) não importa
estas funções — ele sobe este servidor como subprocesso, descobre as
ferramentas via protocolo MCP (list_tools) e as executa via call_tool.

Uso:  python -m camposync.servidor_mcp     (transporte stdio)

Importante: no transporte stdio o stdout é o canal do protocolo — nada
neste processo pode usar print() para stdout (use stderr).
"""
import sqlite3, os
from datetime import date, datetime
from typing import Optional
from fastmcp import FastMCP

from .config import DB_PATH
from . import rag

mcp = FastMCP("consultor-safra")


def _con():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ── 1. Listar fazendas ──────────────────────────────────────────────────────
@mcp.tool()
def listar_fazendas() -> list[dict]:
    """Retorna todas as fazendas cadastradas com área e culturas."""
    with _con() as con:
        rows = con.execute("SELECT id, nome, municipio, area_ha, culturas FROM fazendas").fetchall()
    return [dict(r) for r in rows]


# ── 2. Gastos por safra ─────────────────────────────────────────────────────
@mcp.tool()
def gastos_por_safra(
    fazenda_id: int,
    safra: str,
    cultura: Optional[str] = None,
) -> dict:
    """
    Retorna o total gasto por categoria em uma safra de uma fazenda.
    safra: formato '2024/25'. cultura: 'soja', 'milho' ou 'trigo' (opcional).
    """
    sql = """
        SELECT categoria, SUM(valor) AS total
        FROM lancamentos
        WHERE fazenda_id = ? AND safra = ?
    """
    params: list = [fazenda_id, safra]
    if cultura:
        sql += " AND cultura = ?"
        params.append(cultura)
    sql += " GROUP BY categoria ORDER BY total DESC"

    with _con() as con:
        faz = con.execute("SELECT nome FROM fazendas WHERE id = ?", (fazenda_id,)).fetchone()
        rows = con.execute(sql, params).fetchall()
        total = con.execute(
            "SELECT SUM(valor) FROM lancamentos WHERE fazenda_id=? AND safra=?" + (" AND cultura=?" if cultura else ""),
            params,
        ).fetchone()[0] or 0

    return {
        "fazenda": faz["nome"] if faz else "desconhecida",
        "safra": safra,
        "cultura": cultura or "todas",
        "total_gasto": round(total, 2),
        "por_categoria": [{"categoria": r["categoria"], "total": round(r["total"], 2)} for r in rows],
    }


# ── 3. Comparar safras ──────────────────────────────────────────────────────
@mcp.tool()
def comparar_safras(
    fazenda_id: int,
    safra_a: str,
    safra_b: str,
    cultura: Optional[str] = None,
) -> dict:
    """
    Compara gastos entre duas safras, retornando variação por categoria.
    Útil para responder 'por que minha safra custou mais?'.
    """
    def _gastos(safra):
        sql = "SELECT categoria, SUM(valor) AS t FROM lancamentos WHERE fazenda_id=? AND safra=?"
        p = [fazenda_id, safra]
        if cultura:
            sql += " AND cultura=?"
            p.append(cultura)
        sql += " GROUP BY categoria"
        with _con() as con:
            return {r["categoria"]: r["t"] for r in con.execute(sql, p).fetchall()}

    ga, gb = _gastos(safra_a), _gastos(safra_b)
    cats = sorted(set(ga) | set(gb))
    comparacao = []
    for c in cats:
        va, vb = ga.get(c, 0), gb.get(c, 0)
        var = ((vb - va) / va * 100) if va else None
        comparacao.append({"categoria": c, safra_a: round(va, 2), safra_b: round(vb, 2),
                            "variacao_pct": round(var, 1) if var is not None else None})

    total_a = sum(ga.values())
    total_b = sum(gb.values())
    var_total = (total_b - total_a) / total_a * 100 if total_a else None

    return {
        "fazenda_id": fazenda_id,
        "cultura": cultura or "todas",
        "total": {safra_a: round(total_a, 2), safra_b: round(total_b, 2),
                  "variacao_pct": round(var_total, 1) if var_total is not None else None},
        "por_categoria": comparacao,
    }


# ── 4. Resultado da safra (receita - despesa) ───────────────────────────────
@mcp.tool()
def resultado_safra(fazenda_id: int, safra: str, cultura: Optional[str] = None) -> dict:
    """
    Calcula receita bruta, despesa total e margem de uma safra.
    """
    p_base = [fazenda_id, safra]
    filtro_cult = " AND cultura=?" if cultura else ""
    p = p_base + ([cultura] if cultura else [])

    with _con() as con:
        faz = con.execute("SELECT nome FROM fazendas WHERE id=?", (fazenda_id,)).fetchone()
        despesa = con.execute(
            "SELECT COALESCE(SUM(valor),0) FROM lancamentos WHERE fazenda_id=? AND safra=?" + filtro_cult, p
        ).fetchone()[0]
        receita = con.execute(
            "SELECT COALESCE(SUM(valor),0) FROM receitas WHERE fazenda_id=? AND safra=?" + filtro_cult, p
        ).fetchone()[0]
        prod = con.execute(
            "SELECT SUM(producao_sacas) sacas, AVG(produtividade_sc_ha) prod FROM plantios WHERE fazenda_id=? AND safra=?" + filtro_cult, p
        ).fetchone()

    margem = receita - despesa
    return {
        "fazenda": faz["nome"] if faz else "desconhecida",
        "safra": safra,
        "cultura": cultura or "todas",
        "receita_bruta": round(receita, 2),
        "despesa_total": round(despesa, 2),
        "margem_bruta": round(margem, 2),
        "margem_pct": round(margem / receita * 100, 1) if receita else None,
        "producao_sacas": prod["sacas"],
        "produtividade_sc_ha": round(prod["prod"], 1) if prod["prod"] else None,
    }


# ── 5. Cotação atual ─────────────────────────────────────────────────────────
@mcp.tool()
def cotacao_atual(produto: str) -> dict:
    """
    Retorna a cotação mais recente de um produto: 'soja', 'milho' ou 'trigo'.
    """
    with _con() as con:
        row = con.execute(
            "SELECT data, preco_saca, praca FROM cotacoes WHERE produto=? ORDER BY data DESC LIMIT 1",
            (produto.lower(),),
        ).fetchone()
    if not row:
        return {"erro": f"produto '{produto}' não encontrado"}
    return {"produto": produto, "data": row["data"], "preco_saca": row["preco_saca"], "praca": row["praca"]}


# ── 6. Histórico de cotações ─────────────────────────────────────────────────
@mcp.tool()
def historico_cotacoes(produto: str, safra: str) -> list[dict]:
    """
    Retorna as cotações semanais de um produto durante uma safra específica.
    safra: '2024/25'
    """
    ano = int(safra[:4])
    inicio = f"{ano}-07-01"
    fim = f"{ano + 1}-06-30"
    with _con() as con:
        rows = con.execute(
            "SELECT data, preco_saca FROM cotacoes WHERE produto=? AND data BETWEEN ? AND ? ORDER BY data",
            (produto.lower(), inicio, fim),
        ).fetchall()
    return [dict(r) for r in rows]


# ── 7. Detectar anomalias ────────────────────────────────────────────────────
@mcp.tool()
def detectar_anomalias(fazenda_id: int) -> list[dict]:
    """
    Compara o gasto de cada categoria/safra com a média histórica da fazenda.
    Retorna itens com desvio acima de 20%.
    """
    with _con() as con:
        rows = con.execute("""
            SELECT safra, cultura, categoria,
                   SUM(valor) AS total,
                   AVG(SUM(valor)) OVER (PARTITION BY cultura, categoria) AS media
            FROM lancamentos
            WHERE fazenda_id=?
            GROUP BY safra, cultura, categoria
        """, (fazenda_id,)).fetchall()

    alertas = []
    for r in rows:
        if r["media"] and r["media"] > 0:
            desvio = (r["total"] - r["media"]) / r["media"] * 100
            if abs(desvio) > 20:
                alertas.append({
                    "safra": r["safra"], "cultura": r["cultura"],
                    "categoria": r["categoria"],
                    "total": round(r["total"], 2),
                    "media_historica": round(r["media"], 2),
                    "desvio_pct": round(desvio, 1),
                })
    return sorted(alertas, key=lambda x: abs(x["desvio_pct"]), reverse=True)


# ── 8. Buscar lançamentos ────────────────────────────────────────────────────
@mcp.tool()
def buscar_lancamentos(
    fazenda_id: int,
    safra: Optional[str] = None,
    categoria: Optional[str] = None,
    limite: int = 20,
) -> list[dict]:
    """
    Busca lançamentos individuais com filtro por fazenda, safra e/ou categoria.
    """
    sql = "SELECT id, data, cultura, categoria, fornecedor, valor, mensagem_whatsapp FROM lancamentos WHERE fazenda_id=?"
    p: list = [fazenda_id]
    if safra:
        sql += " AND safra=?"; p.append(safra)
    if categoria:
        sql += " AND categoria LIKE ?"; p.append(f"%{categoria}%")
    sql += f" ORDER BY data DESC LIMIT {int(limite)}"
    with _con() as con:
        rows = con.execute(sql, p).fetchall()
    return [dict(r) for r in rows]


# ── 9. Recomendar ações com base no histórico ────────────────────────────────
@mcp.tool()
def recomendar_acoes(fazenda_id: int) -> list[dict]:
    """
    Analisa o histórico financeiro da fazenda e gera recomendações práticas
    baseadas em padrões de custo, margens e sazonalidade das safras anteriores.
    """
    with _con() as con:
        faz = con.execute("SELECT nome FROM fazendas WHERE id=?", (fazenda_id,)).fetchone()

        # Tendência de gasto por categoria/safra
        tendencia = con.execute("""
            SELECT safra, cultura, categoria, SUM(valor) AS total
            FROM lancamentos WHERE fazenda_id=?
            GROUP BY safra, cultura, categoria
            ORDER BY safra, cultura, categoria
        """, (fazenda_id,)).fetchall()

        # Margens por safra/cultura
        margens = con.execute("""
            SELECT p.safra, p.cultura,
                   COALESCE((SELECT SUM(valor) FROM receitas r
                              WHERE r.fazenda_id=p.fazenda_id AND r.safra=p.safra AND r.cultura=p.cultura), 0) AS receita,
                   COALESCE((SELECT SUM(valor) FROM lancamentos l
                              WHERE l.fazenda_id=p.fazenda_id AND l.safra=p.safra AND l.cultura=p.cultura), 0) AS despesa,
                   p.produtividade_sc_ha
            FROM plantios p
            WHERE p.fazenda_id=?
            ORDER BY p.safra, p.cultura
        """, (fazenda_id,)).fetchall()

        # Sazonalidade: mês de maior gasto por categoria
        sazonalidade = con.execute("""
            SELECT categoria, strftime('%m', data) AS mes, AVG(valor) AS media
            FROM lancamentos WHERE fazenda_id=?
            GROUP BY categoria, mes
            ORDER BY categoria, media DESC
        """, (fazenda_id,)).fetchall()

    recomendacoes = []
    meses = {"01":"janeiro","02":"fevereiro","03":"março","04":"abril","05":"maio",
              "06":"junho","07":"julho","08":"agosto","09":"setembro",
              "10":"outubro","11":"novembro","12":"dezembro"}

    # Agrupa tendência por (cultura, categoria) → lista de (safra, total)
    from collections import defaultdict
    historico = defaultdict(list)
    for safra, cultura, cat, total in tendencia:
        historico[(cultura, cat)].append((safra, total))

    for (cultura, cat), series in historico.items():
        if len(series) < 2:
            continue
        series.sort()
        media = sum(t for _, t in series) / len(series)
        ultimo = series[-1][1]
        if media > 0 and ultimo > media * 1.15:
            pct = round((ultimo / media - 1) * 100)
            recomendacoes.append({
                "tipo": "alerta_custo",
                "cultura": cultura,
                "categoria": cat,
                "mensagem": (
                    f"Gastos com {cat} ({cultura}) na última safra estão {pct}% acima da média histórica "
                    f"(R$ {round(ultimo):,} vs média R$ {round(media):,}). "
                    f"Avalie renegociar com fornecedores ou comparar preços antes do próximo plantio."
                ),
                "prioridade": "alta" if pct >= 25 else "media",
            })

    # Melhor/pior safra
    margens_calc = [
        (r[0], r[1], round(r[2] - r[3], 2), r[4])
        for r in margens if r[2] > 0
    ]
    if margens_calc:
        melhor = max(margens_calc, key=lambda x: x[2])
        pior   = min(margens_calc, key=lambda x: x[2])
        recomendacoes.append({
            "tipo": "benchmark_interno",
            "mensagem": (
                f"Sua melhor margem foi na safra {melhor[0]} com {melhor[1]}: "
                f"R$ {melhor[2]:,}. Analise o que foi diferente (clima, preço de venda, controle de custo) "
                f"para tentar replicar nas próximas safras."
            ),
            "prioridade": "media",
        })
        if pior[2] < melhor[2] * 0.6 and pior[0] != melhor[0]:
            recomendacoes.append({
                "tipo": "alerta_margem",
                "mensagem": (
                    f"A safra {pior[0]} ({pior[1]}) teve margem de R$ {pior[2]:,}, "
                    f"muito abaixo da melhor safra. Verifique se houve problema climático, "
                    f"queda de produtividade ou aumento atípico de custos nesse período."
                ),
                "prioridade": "alta",
            })

    # Sazonalidade: top mês por categoria
    picos_vistos = set()
    for cat, mes, _ in sazonalidade:
        if cat not in picos_vistos:
            recomendacoes.append({
                "tipo": "sazonalidade",
                "categoria": cat,
                "mensagem": (
                    f"Historicamente seus gastos com {cat} são maiores em {meses.get(mes, mes)}. "
                    f"Planeje o fluxo de caixa com antecedência para esse período."
                ),
                "prioridade": "baixa",
            })
            picos_vistos.add(cat)

    ordem = {"alta": 0, "media": 1, "baixa": 2}
    return sorted(recomendacoes, key=lambda x: ordem[x["prioridade"]])


# ── 10. Detectar lançamentos duplicados ──────────────────────────────────────
@mcp.tool()
def detectar_duplicados(fazenda_id: Optional[int] = None, janela_dias: int = 7) -> dict:
    """
    Procura lançamentos registrados em duplicidade (ex: a mesma nota lançada
    duas vezes ou um upload importado de novo).
    - 'exatos': mesma fazenda, data, cultura, categoria, fornecedor e valor.
    - 'suspeitos': mesmo fornecedor, categoria e valor em datas diferentes,
      com até `janela_dias` dias de distância (provável digitação dupla).
    fazenda_id: opcional; se omitido, verifica todas as fazendas.
    """
    filtro = " WHERE fazenda_id = ?" if fazenda_id is not None else ""
    params = [fazenda_id] if fazenda_id is not None else []

    with _con() as con:
        exatos = con.execute(f"""
            SELECT fazenda_id, safra, cultura, data, categoria, fornecedor, valor,
                   COUNT(*) AS ocorrencias, GROUP_CONCAT(id) AS ids
            FROM lancamentos{filtro}
            GROUP BY fazenda_id, safra, cultura, data, categoria, fornecedor, valor
            HAVING COUNT(*) > 1
            ORDER BY valor DESC
        """, params).fetchall()

        pares = con.execute(f"""
            SELECT a.id AS id_a, b.id AS id_b, a.fazenda_id, a.categoria, a.fornecedor,
                   a.valor, a.data AS data_a, b.data AS data_b
            FROM lancamentos a
            JOIN lancamentos b
              ON a.fazenda_id = b.fazenda_id AND a.fornecedor = b.fornecedor
             AND a.categoria = b.categoria AND a.valor = b.valor
             AND a.data < b.data
             AND julianday(b.data) - julianday(a.data) <= ?
            {"WHERE a.fazenda_id = ?" if fazenda_id is not None else ""}
            ORDER BY a.valor DESC
        """, [janela_dias] + params).fetchall()

    exatos_fmt = []
    for r in exatos:
        ocorr = r["ocorrencias"]
        exatos_fmt.append({
            "fazenda_id": r["fazenda_id"], "safra": r["safra"], "cultura": r["cultura"],
            "data": r["data"], "categoria": r["categoria"], "fornecedor": r["fornecedor"],
            "valor": round(r["valor"], 2), "ocorrencias": ocorr,
            "ids": [int(i) for i in r["ids"].split(",")],
            "valor_em_excesso": round(r["valor"] * (ocorr - 1), 2),
        })

    suspeitos_fmt = [{
        "fazenda_id": r["fazenda_id"], "categoria": r["categoria"], "fornecedor": r["fornecedor"],
        "valor": round(r["valor"], 2), "ids": [r["id_a"], r["id_b"]],
        "datas": [r["data_a"], r["data_b"]],
        "dias_entre": (datetime.fromisoformat(r["data_b"][:10]) - datetime.fromisoformat(r["data_a"][:10])).days,
    } for r in pares]

    return {
        "fazenda_id": fazenda_id if fazenda_id is not None else "todas",
        "total_exatos": len(exatos_fmt),
        "valor_total_em_excesso": round(sum(d["valor_em_excesso"] for d in exatos_fmt), 2),
        "exatos": exatos_fmt,
        "total_suspeitos": len(suspeitos_fmt),
        "suspeitos": suspeitos_fmt,
    }


# ── 11. Base de conhecimento (RAG) ───────────────────────────────────────────
@mcp.tool()
def buscar_documentos(consulta: str, n_resultados: int = 4) -> list[dict]:
    """
    Busca trechos relevantes na base de conhecimento do agro (PDFs da Embrapa,
    Conab, artigos sobre custos de soja/milho no RS, LCDPR). Use para perguntas
    conceituais, técnicas ou de referência de mercado — não para dados da fazenda.
    Retorna o texto de cada trecho com o documento de origem e a página.
    """
    return rag.buscar_documentos(consulta, n_resultados)


if __name__ == "__main__":
    import threading
    # Constrói o índice do RAG em segundo plano enquanto o servidor já atende
    # as outras ferramentas (a 1ª indexação dos PDFs leva alguns minutos).
    threading.Thread(target=rag.aquecer, daemon=True, name="rag-aquecer").start()
    mcp.run(show_banner=False)
    # O cliente fechou o stdin: encerra já. Sem isso, threads internas do
    # ChromaDB/ONNX mantêm o processo vivo e quem o abriu fica esperando.
    os._exit(0)
