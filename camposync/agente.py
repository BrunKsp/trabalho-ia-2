"""
Agente Consultor da Safra
Combina as ferramentas MCP com uma base RAG (documentos do agro)
para responder perguntas do produtor em linguagem natural.

Uso:  python -m camposync.agente
"""
import os, json, textwrap, time
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from .rag import buscar_documentos

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

from .servidor_mcp import (
    listar_fazendas,
    gastos_por_safra,
    comparar_safras,
    resultado_safra,
    cotacao_atual,
    historico_cotacoes,
    detectar_anomalias,
    buscar_lancamentos,
    recomendar_acoes,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "listar_fazendas",
            "description": "Retorna todas as fazendas cadastradas com área e culturas.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gastos_por_safra",
            "description": "Retorna gasto total por categoria em uma safra de uma fazenda.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fazenda_id": {"type": "integer", "description": "ID da fazenda"},
                    "safra": {"type": "string", "description": "ex: '2024/25'"},
                    "cultura": {"type": "string", "description": "'soja', 'milho' ou 'trigo' (opcional)"},
                },
                "required": ["fazenda_id", "safra"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comparar_safras",
            "description": "Compara gastos entre duas safras mostrando variação por categoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fazenda_id": {"type": "integer"},
                    "safra_a": {"type": "string"},
                    "safra_b": {"type": "string"},
                    "cultura": {"type": "string"},
                },
                "required": ["fazenda_id", "safra_a", "safra_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resultado_safra",
            "description": "Calcula receita bruta, despesa total e margem de uma safra.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fazenda_id": {"type": "integer"},
                    "safra": {"type": "string"},
                    "cultura": {"type": "string"},
                },
                "required": ["fazenda_id", "safra"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cotacao_atual",
            "description": "Retorna cotação mais recente de 'soja', 'milho' ou 'trigo'.",
            "parameters": {
                "type": "object",
                "properties": {"produto": {"type": "string"}},
                "required": ["produto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "historico_cotacoes",
            "description": "Retorna cotações semanais de um produto durante uma safra.",
            "parameters": {
                "type": "object",
                "properties": {
                    "produto": {"type": "string"},
                    "safra": {"type": "string"},
                },
                "required": ["produto", "safra"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detectar_anomalias",
            "description": "Detecta gastos anômalos (>20% acima da média histórica) em uma fazenda.",
            "parameters": {
                "type": "object",
                "properties": {"fazenda_id": {"type": "integer"}},
                "required": ["fazenda_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_lancamentos",
            "description": "Busca lançamentos individuais com filtro por fazenda, safra e/ou categoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fazenda_id": {"type": "integer"},
                    "safra": {"type": "string"},
                    "categoria": {"type": "string"},
                    "limite": {"type": "integer"},
                },
                "required": ["fazenda_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_documentos",
            "description": "Busca trechos relevantes na base de conhecimento do agro (Embrapa, Conab, LCDPR).",
            "parameters": {
                "type": "object",
                "properties": {"consulta": {"type": "string"}},
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recomendar_acoes",
            "description": "Analisa o histórico financeiro da fazenda e gera recomendações práticas baseadas em padrões de custo, margens e sazonalidade das safras anteriores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fazenda_id": {"type": "integer", "description": "ID da fazenda"},
                },
                "required": ["fazenda_id"],
            },
        },
    },
]

TOOL_FN = {
    "listar_fazendas": lambda args: listar_fazendas(),
    "gastos_por_safra": lambda args: gastos_por_safra(**args),
    "comparar_safras": lambda args: comparar_safras(**args),
    "resultado_safra": lambda args: resultado_safra(**args),
    "cotacao_atual": lambda args: cotacao_atual(**args),
    "historico_cotacoes": lambda args: historico_cotacoes(**args),
    "detectar_anomalias": lambda args: detectar_anomalias(**args),
    "buscar_lancamentos": lambda args: buscar_lancamentos(**args),
    "buscar_documentos": lambda args: buscar_documentos(**args),
    "recomendar_acoes": lambda args: recomendar_acoes(**args),
}

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
                    tools=TOOLS,
                    tool_choice="auto",
                )
            except RateLimitError:
                wait = 5 * (attempt + 1)
                print(f"  [429] {model} — aguardando {wait}s (tentativa {attempt + 1}/3)")
                time.sleep(wait)
        print(f"  [skip] {model} esgotado, tentando próximo...")
    raise RuntimeError("Todos os modelos free atingiram o rate limit. Tente novamente em alguns minutos.")


def executar_ferramenta(nome: str, args: dict) -> str:
    fn = TOOL_FN.get(nome)
    if not fn:
        return json.dumps({"erro": f"ferramenta '{nome}' não encontrada"})
    try:
        resultado = fn(args)
        return json.dumps(resultado, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": str(e)})


def perguntar(mensagens: list) -> str:
    """Envia mensagens para o agente e processa chamadas de ferramentas."""
    messages = [{"role": "system", "content": SYSTEM}]
    for msg in mensagens:
        content = msg["content"]
        if isinstance(content, str):
            messages.append({"role": msg["role"], "content": content})

    while True:
        response = _create_with_fallback(messages)

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or "(sem resposta)"

        # Adiciona a resposta do modelo com as tool_calls ao histórico
        messages.append(msg)

        # Executa cada ferramenta e adiciona os resultados
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"  [ferramenta] {tc.function.name}({args})")
            result = executar_ferramenta(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })


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
