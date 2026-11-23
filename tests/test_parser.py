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
