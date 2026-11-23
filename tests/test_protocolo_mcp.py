"""
Testes do servidor pelo PROTOCOLO MCP, do jeito que o agente o usa:
subprocesso via stdio, list_tools e call_tool (camposync/cliente_mcp.py).
"""
import json

import pytest

from camposync import servidor_mcp as s
from camposync.cliente_mcp import get_cliente, chamar
from camposync.agente import ferramentas_openai, executar_ferramenta

ESPERADAS = {
    "listar_fazendas", "gastos_por_safra", "comparar_safras", "resultado_safra",
    "cotacao_atual", "historico_cotacoes", "detectar_anomalias", "buscar_lancamentos",
    "recomendar_acoes", "detectar_duplicados", "buscar_documentos",
}


def test_list_tools_anuncia_todas_as_ferramentas():
    nomes = {t.name for t in get_cliente().listar_ferramentas()}
    assert nomes == ESPERADAS


def test_ferramentas_tem_descricao_e_schema():
    for t in ferramentas_openai():
        f = t["function"]
        assert len(f["description"]) > 20, f"{f['name']} sem descrição útil para o LLM"
        assert f["parameters"]["type"] == "object"


def test_schema_marca_parametros_obrigatorios():
    tools = {t["function"]["name"]: t["function"]["parameters"] for t in ferramentas_openai()}
    assert set(tools["gastos_por_safra"]["required"]) == {"fazenda_id", "safra"}
    assert "required" not in tools["detectar_duplicados"] or not tools["detectar_duplicados"]["required"]


@pytest.mark.parametrize("nome, args, direto", [
    ("listar_fazendas", {}, lambda: s.listar_fazendas()),
    ("resultado_safra", {"fazenda_id": 1, "safra": "2024/25"}, lambda: s.resultado_safra(1, "2024/25")),
    ("detectar_anomalias", {"fazenda_id": 3}, lambda: s.detectar_anomalias(3)),
    ("detectar_duplicados", {"fazenda_id": 1}, lambda: s.detectar_duplicados(1)),
])
def test_call_tool_igual_a_chamada_direta(nome, args, direto):
    """O resultado via protocolo é idêntico ao da função — nada se perde na serialização."""
    assert chamar(nome, args) == direto()


def test_erro_de_validacao_volta_como_json_para_o_llm():
    r = json.loads(executar_ferramenta("gastos_por_safra", {"safra": "2024/25"}))  # falta fazenda_id
    assert "erro" in r and "fazenda_id" in r["erro"]


def test_ferramenta_inexistente():
    r = json.loads(executar_ferramenta("nao_existe", {}))
    assert "erro" in r


@pytest.mark.lento
def test_rag_via_mcp_retorna_fonte_e_pagina():
    trechos = chamar("buscar_documentos", {"consulta": "custo de produção da soja por hectare", "n_resultados": 3})
    assert len(trechos) == 3
    for t in trechos:
        assert t["fonte"].endswith(".pdf")
        assert int(t["pagina"]) >= 1
        assert len(t["texto"]) > 50
