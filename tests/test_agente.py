"""
Testes do laço do agente SEM chamar o LLM de verdade.

Um LLM falso, roteirizado, devolve as respostas na ordem definida pelo teste.
Assim verificamos de forma determinística: execução das ferramentas via MCP,
coleta das fontes do RAG, limite de rodadas, troca de modelo em caso de erro e
gravação do log, sem gastar cota nem depender da rede.
"""
import json
from types import SimpleNamespace as NS

import httpx
import openai
import pytest

from camposync import agente


# ── LLM falso ────────────────────────────────────────────────────────────────
def _tool_call(nome, args, i=0):
    return NS(id=f"call_{i}", type="function", function=NS(name=nome, arguments=json.dumps(args)))


def _resp(conteudo=None, tool_calls=None, modelo="modelo/falso"):
    return NS(model=modelo, choices=[NS(message=NS(role="assistant", content=conteudo, tool_calls=tool_calls))])


def _erro(cls, status):
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return cls("erro simulado", response=httpx.Response(status, request=req), body=None)


class LLMFalso:
    """Cada item do roteiro é uma resposta ou uma exceção (consumidos em ordem)."""

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.chamadas = []  # (modelo, tinha_ferramentas)
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, model, messages, **kw):
        self.chamadas.append((model, "tools" in kw))
        item = self.roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _isolar(monkeypatch, tmp_path):
    monkeypatch.setattr(agente, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(agente, "_ultimo_ok", None)
    monkeypatch.setattr(agente, "_bloqueado_ate", {})
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr(agente.time, "sleep", lambda s: None)


def _usar(monkeypatch, roteiro) -> LLMFalso:
    llm = LLMFalso(roteiro)
    monkeypatch.setattr(agente, "_get_client", lambda: llm)
    return llm


PERGUNTA = [{"role": "user", "content": "[Fazenda selecionada: Fazenda Boa Vista (id=1)] Tem duplicado?"}]


# ── Testes ───────────────────────────────────────────────────────────────────
def test_executa_ferramenta_via_mcp_e_responde(monkeypatch):
    _usar(monkeypatch, [
        _resp(tool_calls=[_tool_call("detectar_duplicados", {"fazenda_id": 1})]),
        _resp("Encontrei 1 duplicado de R$ 15.854,30."),
    ])
    r = agente.perguntar_detalhado(PERGUNTA)
    assert r["resposta"].startswith("Encontrei 1 duplicado")
    assert [f["nome"] for f in r["ferramentas"]] == ["detectar_duplicados"]
    resultado = json.loads(r["ferramentas"][0]["resultado"])
    assert resultado["valor_total_em_excesso"] == pytest.approx(15854.30)


def test_ferramenta_recebe_resultado_no_historico(monkeypatch):
    """O resultado da ferramenta precisa voltar ao modelo como mensagem 'tool'."""
    capturadas = []
    llm = _usar(monkeypatch, [
        _resp(tool_calls=[_tool_call("listar_fazendas", {})]),
        _resp("ok"),
    ])
    original = llm._create

    def espiao(model, messages, **kw):
        capturadas.append(list(messages))
        return original(model, messages, **kw)

    llm.chat.completions.create = espiao
    agente.perguntar_detalhado(PERGUNTA)
    ultima = capturadas[-1][-1]
    assert ultima["role"] == "tool" and ultima["tool_call_id"] == "call_0"
    assert "Fazenda Boa Vista" in ultima["content"]


def test_argumentos_invalidos_nao_quebram(monkeypatch):
    tc = NS(id="c", type="function", function=NS(name="listar_fazendas", arguments="{isso não é json"))
    _usar(monkeypatch, [_resp(tool_calls=[tc]), _resp("ok")])
    assert agente.perguntar_detalhado(PERGUNTA)["resposta"] == "ok"


def test_coleta_fontes_do_rag(monkeypatch):
    trechos = [{"texto": "custo por hectare...", "fonte": "embrapa.pdf", "pagina": 9}]
    monkeypatch.setattr(agente, "executar_ferramenta", lambda nome, args: json.dumps(trechos))
    _usar(monkeypatch, [
        _resp(tool_calls=[_tool_call("buscar_documentos", {"consulta": "custo soja"})]),
        _resp("Segundo a Embrapa..."),
    ])
    r = agente.perguntar_detalhado(PERGUNTA)
    assert r["fontes"] == [{"fonte": "embrapa.pdf", "pagina": 9, "texto": "custo por hectare..."}]


def test_limite_de_rodadas_forca_resposta_final(monkeypatch):
    """Modelo em ciclo de ferramentas: após MAX_RODADAS pede resposta sem ferramentas."""
    roteiro = [_resp(tool_calls=[_tool_call("listar_fazendas", {}, i)]) for i in range(agente.MAX_RODADAS)]
    llm = _usar(monkeypatch, roteiro + [_resp("Resposta com o que tenho.")])
    r = agente.perguntar_detalhado(PERGUNTA)
    assert r["resposta"] == "Resposta com o que tenho."
    assert len(r["ferramentas"]) == agente.MAX_RODADAS
    assert llm.chamadas[-1][1] is False  # última chamada sem tools


def test_429_troca_de_modelo_sem_esperar(monkeypatch):
    llm = _usar(monkeypatch, [_erro(openai.RateLimitError, 429), _resp("ok")])
    agente.perguntar_detalhado(PERGUNTA)
    assert [m for m, _ in llm.chamadas] == agente.FREE_MODELS[:2]
    assert agente._ultimo_ok == agente.FREE_MODELS[1]
    assert agente.FREE_MODELS[0] in agente._bloqueado_ate


def test_proxima_pergunta_comeca_pelo_modelo_que_funcionou(monkeypatch):
    llm = _usar(monkeypatch, [_erro(openai.RateLimitError, 429), _resp("a"), _resp("b")])
    agente.perguntar_detalhado(PERGUNTA)
    agente.perguntar_detalhado(PERGUNTA)
    assert llm.chamadas[-1][0] == agente.FREE_MODELS[1]


def test_erro_do_provedor_passa_ao_proximo(monkeypatch):
    llm = _usar(monkeypatch, [_erro(openai.InternalServerError, 503), _resp("ok")])
    assert agente.perguntar_detalhado(PERGUNTA)["resposta"] == "ok"
    assert len(llm.chamadas) == 2


def test_modelo_preferido_do_env_vem_primeiro(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "pago/modelo-estavel")
    llm = _usar(monkeypatch, [_resp("ok")])
    agente.perguntar_detalhado(PERGUNTA)
    assert llm.chamadas[0][0] == "pago/modelo-estavel"


def test_chave_invalida_para_imediatamente(monkeypatch):
    llm = _usar(monkeypatch, [_erro(openai.AuthenticationError, 401)])
    with pytest.raises(RuntimeError, match="inválida"):
        agente.perguntar_detalhado(PERGUNTA)
    assert len(llm.chamadas) == 1


def test_todos_ocupados_gera_erro_amigavel(monkeypatch):
    n = len(agente.FREE_MODELS) * 3
    _usar(monkeypatch, [_erro(openai.RateLimitError, 429) for _ in range(n)])
    with pytest.raises(RuntimeError, match="Nenhum modelo respondeu"):
        agente.perguntar_detalhado(PERGUNTA)


def test_sem_chave_mensagem_clara(monkeypatch):
    monkeypatch.setattr(agente, "_client", None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        agente._get_client()


def test_grava_log_da_conversa(monkeypatch):
    _usar(monkeypatch, [
        _resp(tool_calls=[_tool_call("detectar_anomalias", {"fazenda_id": 1})]),
        _resp("Fertilizante 28% acima."),
    ])
    agente.perguntar_detalhado(PERGUNTA)
    logs = list(agente.LOGS_DIR.glob("*.jsonl"))
    assert len(logs) == 1
    reg = json.loads(logs[0].read_text(encoding="utf-8").strip().splitlines()[-1])
    assert reg["pergunta"] == PERGUNTA[0]["content"]
    assert reg["ferramentas"][0]["nome"] == "detectar_anomalias"
    assert reg["resposta"] == "Fertilizante 28% acima."
