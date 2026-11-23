"""Testes da importação de planilhas (CSV/Excel) — sem LLM."""
import sqlite3

import pandas as pd
import pytest

from camposync.parser_documentos import (
    _mapear_dataframe, extrair_lancamentos_csv, importar_lancamentos,
)


def test_mapeia_colunas_com_nomes_variados():
    df = pd.DataFrame({
        "Data": ["2025-10-01"], "VALOR": ["R$ 1500,50"], "Categoria": ["Sementes"],
        "Empresa": ["Coop X"], "Cultura": ["Soja"], "Safra": ["2025/26"],
    })
    [l] = _mapear_dataframe(df)
    assert l == {"data": "2025-10-01", "valor": 1500.50, "categoria": "Sementes",
                 "fornecedor": "Coop X", "cultura": "soja", "safra": "2025/26"}


def test_sem_data_ou_valor_nao_importa():
    assert _mapear_dataframe(pd.DataFrame({"fornecedor": ["x"], "valor": [10]})) == []


def test_linha_com_valor_invalido_e_ignorada():
    df = pd.DataFrame({"data": ["2025-01-01", "2025-01-02"], "valor": ["100", "abc"]})
    assert len(_mapear_dataframe(df)) == 1


def test_csv_com_ponto_e_virgula(tmp_path):
    arq = tmp_path / "lanc.csv"
    arq.write_text("data;valor;categoria\n2025-11-01;250.00;Defensivos\n", encoding="utf-8")
    [l] = extrair_lancamentos_csv(str(arq))
    assert l["valor"] == 250.0 and l["categoria"] == "Defensivos"


def test_importa_no_banco_de_teste(db_teste):
    con = sqlite3.connect(db_teste)
    antes = con.execute("SELECT COUNT(*) FROM lancamentos").fetchone()[0]
    try:
        n = importar_lancamentos([
            {"data": "2026-01-10", "valor": 99.9, "categoria": "Sementes", "fornecedor": "Teste",
             "cultura": "soja", "safra": "2025/26"},
        ], fazenda_id=2)
        assert n == 1
        assert con.execute("SELECT COUNT(*) FROM lancamentos").fetchone()[0] == antes + 1
        origem = con.execute("SELECT mensagem_whatsapp FROM lancamentos ORDER BY id DESC LIMIT 1").fetchone()[0]
        assert origem == "importado via upload"
    finally:
        con.execute("DELETE FROM lancamentos WHERE fornecedor='Teste'")
        con.commit()
        con.close()


def test_lista_vazia():
    assert importar_lancamentos([], fazenda_id=1) == 0


# ── PDF (LLM) ────────────────────────────────────────────────────────────────
from camposync.parser_documentos import _parse_json_lancamentos  # noqa: E402


def test_parse_json_com_cerca_de_codigo_e_texto():
    resposta = 'Aqui estão:\n```json\n[{"data": "2025-10-12", "valor": 98400.0, "categoria": "Fertilizantes"}]\n```'
    assert _parse_json_lancamentos(resposta)[0]["valor"] == 98400.0


def test_parse_json_varios_objetos():
    resposta = '[{"valor": 1, "data": "a"}, {"valor": 2, "data": "b"}]'
    assert [d["valor"] for d in _parse_json_lancamentos(resposta)] == [1, 2]


def test_parse_json_invalido_ou_vazio():
    assert _parse_json_lancamentos("não encontrei nada") == []
    assert _parse_json_lancamentos("[isso não é json]") == []
    assert _parse_json_lancamentos('[{"sem_valor": 1}]') == []


def test_pdf_usa_fallback_de_modelos(monkeypatch, tmp_path):
    """O PDF vai pelo mesmo _create_with_fallback do agente (troca de modelo em 429)."""
    from types import SimpleNamespace as NS
    import camposync.agente as agente
    import camposync.parser_documentos as pd_mod

    texto = "NOTA FISCAL Cooperativa X 12/10/2025 Fertilizante NPK R$ 98.400,00 safra 2025/26 soja " * 2
    monkeypatch.setattr(pd_mod, "PdfReader", lambda path: NS(pages=[NS(extract_text=lambda: texto)]))
    chamadas = []

    def falso(messages, usar_ferramentas=True):
        chamadas.append(usar_ferramentas)
        return NS(choices=[NS(message=NS(content='[{"data": "2025-10-12", "valor": 98400.0}]'))])

    monkeypatch.setattr(agente, "_create_with_fallback", falso)
    r = pd_mod.extrair_lancamentos_pdf(str(tmp_path / "nota.pdf"))
    assert r == [{"data": "2025-10-12", "valor": 98400.0}]
    assert chamadas == [False]  # sem ferramentas


def test_pdf_erro_do_modelo_sobe_para_a_interface(monkeypatch, tmp_path):
    from types import SimpleNamespace as NS
    import camposync.agente as agente
    import camposync.parser_documentos as pd_mod

    monkeypatch.setattr(pd_mod, "PdfReader", lambda path: NS(pages=[NS(extract_text=lambda: "x" * 100)]))

    def falha(messages, usar_ferramentas=True):
        raise RuntimeError("Nenhum modelo respondeu agora")

    monkeypatch.setattr(agente, "_create_with_fallback", falha)
    with pytest.raises(RuntimeError, match="Nenhum modelo"):
        pd_mod.extrair_lancamentos_pdf(str(tmp_path / "nota.pdf"))
