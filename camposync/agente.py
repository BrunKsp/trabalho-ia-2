"""
Agente Consultor da Safra
Combina as ferramentas MCP com uma base RAG (documentos do agro)
para responder perguntas do produtor em linguagem natural.

Uso:  python -m camposync.agente
"""
import os, json, textwrap, time
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from .cliente_mcp import get_cliente

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
    base_url="https://openrouter.ai/api/v1",
)

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
                    "parameters": t.inputSchema or {"type": "object", "properties": {}},
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


def _create_with_fallback(messages: list):
    """Tenta cada modelo free em sequência; faz retry com backoff em 429."""
    for model in FREE_MODELS:
        for attempt in range(3):
            try:
                return client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=ferramentas_openai(),
                    tool_choice="auto",
                )
            except RateLimitError:
                wait = 5 * (attempt + 1)
                print(f"  [429] {model} — aguardando {wait}s (tentativa {attempt + 1}/3)")
                time.sleep(wait)
        print(f"  [skip] {model} esgotado, tentando próximo...")
    raise RuntimeError("Todos os modelos free atingiram o rate limit. Tente novamente em alguns minutos.")


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

    while True:
        response = _create_with_fallback(messages)
        modelo = getattr(response, "model", None) or modelo

        msg = response.choices[0].message

        if not msg.tool_calls:
            return {
                "resposta": msg.content or "(sem resposta)",
                "ferramentas": ferramentas,
                "fontes": fontes,
                "modelo": modelo,
            }

        # Adiciona a resposta do modelo com as tool_calls ao histórico
        messages.append(msg)

        # Executa cada ferramenta e adiciona os resultados
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
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
