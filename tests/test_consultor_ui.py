"""Testes da lógica da página do Consultor (sem navegador e sem LLM)."""
import json
import sqlite3

import pytest

from camposync import servidor_mcp as s
from ui import dados
from ui.paginas import consultor as c


def test_data_e_percentual_no_padrao_brasileiro():
    assert c._data_br("2023-10-05") == "05/10/2023"
    assert c._data_br("2023-10-05T00:00:00") == "05/10/2023"
    assert c._pct(33.07) == "+33,1%"
    assert c._pct(-11.3) == "-11,3%"


def test_contexto_dos_argumentos_sem_nomes_tecnicos():
    assert c._contexto_args({"fazenda_id": 1, "safra": "2025/26", "cultura": "soja"}) == "safra 2025/26 · soja"
    assert c._contexto_args({"fazenda_id": 1}) == ""


@pytest.mark.parametrize("nome, chamada, esperado", [
    ("detectar_duplicados", lambda: s.detectar_duplicados(1), ["R$ 15.854,30", "05/10/2023", "2 vezes"]),
    ("comparar_safras", lambda: s.comparar_safras(1, "2024/25", "2025/26", "soja"), ["fertilizantes", "+33,1%"]),
    ("resultado_safra", lambda: s.resultado_safra(1, "2024/25"), ["margem", "-11,3%"]),
    ("detectar_anomalias", lambda: s.detectar_anomalias(3), ["defensivos", "2024/25"]),
    ("gastos_por_safra", lambda: s.gastos_por_safra(1, "2025/26", "soja"), ["Total gasto: R$"]),
    ("cotacao_atual", lambda: s.cotacao_atual("soja"), ["por saca"]),
])
def test_resumo_mostra_de_onde_vem_o_numero(nome, chamada, esperado):
    resumo = c._resumo_resultado(nome, json.dumps(chamada(), ensure_ascii=False))
    for trecho in esperado:
        assert trecho in resumo, resumo
    assert "_" not in resumo  # nada de nomes de função / campos internos


def test_resumo_tolera_erro_e_lixo():
    assert c._resumo_resultado("gastos_por_safra", '{"erro": "x"}') == "Não encontrou dados para essa consulta."
    assert c._resumo_resultado("gastos_por_safra", "não é json") == ""
    assert c._resumo_resultado("ferramenta_nova", "{}") == ""


def test_trecho_corta_no_fim_da_palavra():
    texto = "palavra " * 100
    t = c._trecho(texto, 30)
    assert t.endswith("…") and not t[:-1].endswith(" ") and "palavr…" not in t


@pytest.mark.parametrize("erro, esperado", [
    (RuntimeError("Nenhum modelo respondeu agora (x: limite de taxa)."), "muita procura"),
    (RuntimeError("OPENROUTER_API_KEY não configurada."), "não está conectado"),
    (RuntimeError("Chave do OpenRouter inválida ou expirada (OPENROUTER_API_KEY)."), "não está conectado"),
    (RuntimeError("Connection error."), "Sem conexão"),
    (ValueError("qualquer outra coisa"), "Não consegui responder"),
])
def test_mensagem_de_erro_na_lingua_do_produtor(erro, esperado):
    msg = c._mensagem_erro(erro)
    assert esperado in msg
    for tecnico in (".env", "OPENROUTER", "429", "modelo", "Error"):
        assert tecnico not in msg


def test_historico_para_agente_pula_perguntas_sem_resposta():
    chat = [
        {"role": "user", "agente": "q1", "estado": "respondida"},
        {"role": "assistant", "agente": "r1"},
        {"role": "user", "agente": "q2", "estado": "erro"},
        {"role": "user", "agente": "q3", "estado": "pendente"},
    ]
    assert [m["content"] for m in c._historico_para_agente(chat)] == ["q1", "r1", "q3"]


def test_sugestoes_vem_da_propria_fazenda():
    sug = [t for _, t in c._sugestoes({"id": 3})]
    assert any("defensivos" in t and "2024/25" in t for t in sug)  # anomalia plantada da Granja
    assert "Tem algum lançamento duplicado?" in sug
    assert len(sug) <= 5


def test_apagar_e_desfazer_lancamento(db_teste):
    con = sqlite3.connect(db_teste)
    antes = con.execute("SELECT COUNT(*) FROM lancamentos").fetchone()[0]
    linha = dados.apagar_lancamento(637)  # a cópia do seguro duplicado
    assert linha["valor"] == pytest.approx(15854.30)
    assert con.execute("SELECT COUNT(*) FROM lancamentos").fetchone()[0] == antes - 1
    assert s.detectar_duplicados(1)["total_exatos"] == 0
    assert dados.apagar_lancamento(637) is None  # já não existe

    dados.restaurar_lancamento(linha)
    assert con.execute("SELECT COUNT(*) FROM lancamentos").fetchone()[0] == antes
    assert s.detectar_duplicados(1)["total_exatos"] == 1
    con.close()
