"""
Agente Consultor da Safra
Combina as ferramentas MCP com uma base RAG (documentos do agro)
para responder perguntas do produtor em linguagem natural.

Uso:  python -m camposync.agente
"""
import os, json, textwrap, time
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, AuthenticationError, APIConnectionError, APIStatusError
from .cliente_mcp import get_cliente
from .config import LOGS_DIR

load_dotenv()

# Limite de rodadas "modelo pede ferramenta → executa" por pergunta. Evita que um
# modelo gratuito entre em ciclo de chamadas e trave a interface.
MAX_RODADAS = 8

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Cria o cliente sob demanda: sem chave a interface abre normalmente e só o chat avisa."""
    global _client
    if _client is None:
        chave = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not chave:
            raise RuntimeError(
                "OPENROUTER_API_KEY não configurada. Crie um arquivo .env na raiz "
                "(veja .env.example) com a sua chave do OpenRouter."
            )
        _client = OpenAI(api_key=chave, base_url="https://openrouter.ai/api/v1")
    return _client

# Modelos free com function calling — tentados em ordem
FREE_MODELS = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3.5-super-vl:free",
]
MODEL_NAME = FREE_MODELS[0]

# ── Ferramentas: descobertas via protocolo MCP ──────────────────────────────
# O agente NÃO importa as funções do servidor. Ele sobe camposync/servidor_mcp.py
# como subprocesso (stdio), pergunta quais ferramentas existem (list_tools) e as
# executa remotamente (call_tool). Nome, descrição e JSON Schema dos parâmetros
# vêm do próprio servidor — adicionar uma ferramenta lá basta para o agente usá-la.
_tools_cache: list | None = None


def ferramentas_openai() -> list[dict]:
    """Converte as ferramentas anunciadas pelo servidor MCP para o formato de tools da API OpenAI."""
    global _tools_cache
    if _tools_cache is None:
        _tools_cache = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": (t.description or "").strip(),
                    "parameters": getattr(t, "input_schema", None) or t.inputSchema or {"type": "object", "properties": {}},
                },
            }
            for t in get_cliente().listar_ferramentas()
        ]
    return _tools_cache


SYSTEM = textwrap.dedent("""
    Você é o Consultor da Safra, um assistente financeiro especializado em agricultura familiar do RS.
    Responda sempre em português brasileiro, de forma clara e objetiva.
    Use as ferramentas disponíveis para buscar dados reais antes de responder.
    Quando encontrar anomalias ou variações relevantes, explique a causa provável.
    Cite valores em Reais (R$) e percentuais quando relevante.
    Se não souber algo com certeza, diga que não tem dados suficientes.
""").strip()


_ultimo_ok: str | None = None   # modelo que respondeu por último: é tentado primeiro
_bloqueado_ate: dict[str, float] = {}  # modelo -> instante até quando evitar (após 429)
ESPERA_429_S = 90


def _ordem_modelos() -> list[str]:
    """Modelo preferido do .env (OPENROUTER_MODEL) → último que funcionou → demais gratuitos."""
    preferido = os.environ.get("OPENROUTER_MODEL", "").strip()
    ordem = [m for m in (preferido, _ultimo_ok) if m] + FREE_MODELS
    return list(dict.fromkeys(ordem))  # remove repetidos mantendo a ordem


def _create_with_fallback(messages: list, usar_ferramentas: bool = True):
    """
    Tenta os modelos em sequência, sem ficar esperando um modelo congestionado:
    - 429 (limite de taxa): marca o modelo como bloqueado por 90 s e passa ao próximo na hora.
    - Modelo indisponível / erro do provedor / rede: passa ao próximo.
    - Chave inválida: para na hora (trocar de modelo não resolve).
    Se todos estiverem bloqueados, espera um pouco e faz mais uma volta (até 3 voltas).
    """
    global _ultimo_ok
    extra = {"tools": ferramentas_openai(), "tool_choice": "auto"} if usar_ferramentas else {}
    erros: dict[str, str] = {}
    for volta in range(3):
        if volta:
            print(f"  [espera] todos os modelos ocupados — nova tentativa em {5 * volta}s")
            time.sleep(5 * volta)
        for model in _ordem_modelos():
            if volta == 0 and _bloqueado_ate.get(model, 0) > time.time():
                continue  # na 1ª volta pula quem acabou de dar 429
            try:
                resp = _get_client().chat.completions.create(model=model, messages=messages, **extra)
                _ultimo_ok = model
                return resp
            except RateLimitError:
                _bloqueado_ate[model] = time.time() + ESPERA_429_S
                erros[model] = "limite de taxa"
                print(f"  [429] {model} ocupado — tentando o próximo")
            except AuthenticationError as e:
                raise RuntimeError("Chave do OpenRouter inválida ou expirada (OPENROUTER_API_KEY).") from e
            except (APIStatusError, APIConnectionError) as e:
                erros[model] = str(getattr(e, "status_code", "") or type(e).__name__)
                print(f"  [erro] {model} — {erros[model]}; tentando o próximo")
    raise RuntimeError(
        "Nenhum modelo respondeu agora (" + "; ".join(f"{m}: {e}" for m, e in erros.items())
        + "). Tente novamente em alguns minutos ou defina OPENROUTER_MODEL no .env."
    )


def _registrar_log(registro: dict):
    """Grava cada pergunta respondida em data/logs/AAAA-MM-DD.jsonl (auditoria e exemplos de saída)."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        arq = LOGS_DIR / f"{datetime.now():%Y-%m-%d}.jsonl"
        with open(arq, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass  # log nunca pode derrubar a resposta


def executar_ferramenta(nome: str, args: dict) -> str:
    """Executa a ferramenta no servidor MCP e devolve o resultado em JSON (para o LLM)."""
    try:
        resultado = get_cliente().chamar(nome, args)
        return json.dumps(resultado, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)


def perguntar_detalhado(mensagens: list, ao_chamar_ferramenta=None) -> dict:
    """
    Envia mensagens ao agente, executa as ferramentas pedidas e devolve:
      resposta   -> texto final
      ferramentas-> [{"nome", "args", "resultado", "segundos"}] na ordem de execução
      fontes     -> trechos do RAG consultados [{"fonte", "pagina", "texto"}]
      modelo     -> modelo que respondeu
    `ao_chamar_ferramenta(nome, args)` (opcional) é chamado antes de cada ferramenta,
    útil para a interface mostrar o progresso.
    """
    messages = [{"role": "system", "content": SYSTEM}]
    for msg in mensagens:
        content = msg["content"]
        if isinstance(content, str):
            messages.append({"role": msg["role"], "content": content})

    ferramentas, fontes, modelo = [], [], None
    inicio_total = time.time()

    def _finalizar(texto: str) -> dict:
        r = {"resposta": texto or "(sem resposta)", "ferramentas": ferramentas, "fontes": fontes, "modelo": modelo}
        _registrar_log({
            "quando": datetime.now().isoformat(timespec="seconds"),
            "pergunta": next((m["content"] for m in reversed(mensagens) if m.get("role") == "user"), ""),
            "modelo": modelo,
            "segundos": round(time.time() - inicio_total, 1),
            "ferramentas": [{"nome": f["nome"], "args": f["args"], "segundos": f["segundos"]} for f in ferramentas],
            "fontes": sorted({f"{f['fonte']} p.{f['pagina']}" for f in fontes}),
            "resposta": r["resposta"],
        })
        return r

    for _ in range(MAX_RODADAS):
        response = _create_with_fallback(messages)
        modelo = getattr(response, "model", None) or modelo

        msg = response.choices[0].message

        if not msg.tool_calls:
            return _finalizar(msg.content)

        # Adiciona a resposta do modelo com as tool_calls ao histórico
        messages.append(msg)

        # Executa cada ferramenta e adiciona os resultados
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"  [ferramenta] {tc.function.name}({args})")
            if ao_chamar_ferramenta:
                ao_chamar_ferramenta(tc.function.name, args)
            inicio = time.time()
            result = executar_ferramenta(tc.function.name, args)
            ferramentas.append({
                "nome": tc.function.name,
                "args": args,
                "resultado": result,
                "segundos": round(time.time() - inicio, 2),
            })
            if tc.function.name == "buscar_documentos":
                try:
                    for trecho in json.loads(result):
                        if isinstance(trecho, dict) and trecho.get("fonte"):
                            fontes.append({"fonte": trecho["fonte"], "pagina": trecho.get("pagina", ""), "texto": trecho.get("texto", "")})
                except (ValueError, TypeError):
                    pass
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # Estourou o limite de rodadas: pede uma resposta final com o que já foi coletado.
    messages.append({"role": "user", "content": (
        "Limite de consultas atingido. Responda agora com base nos dados já obtidos, "
        "sem chamar mais ferramentas."
    )})
    response = _create_with_fallback(messages, usar_ferramentas=False)
    modelo = getattr(response, "model", None) or modelo
    return _finalizar(response.choices[0].message.content)


def perguntar(mensagens: list) -> str:
    """Versão simples: devolve só o texto da resposta."""
    return perguntar_detalhado(mensagens)["resposta"]


def main():
    print("=" * 60)
    print("  Consultor da Safra — CampoSync Demo")
    print("  Digite 'sair' para encerrar")
    print("=" * 60)

    historico = []
    while True:
        try:
            pergunta = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in ("sair", "exit", "quit"):
            break
        if not pergunta:
            continue

        historico.append({"role": "user", "content": pergunta})
        resposta = perguntar(list(historico))
        historico.append({"role": "assistant", "content": resposta})
        print(f"\nConsultor: {resposta}")


if __name__ == "__main__":
    main()
