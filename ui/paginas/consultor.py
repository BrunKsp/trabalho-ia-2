"""Consultor: chat com o agente, mostrando as ferramentas e fontes usadas em cada resposta."""
import os
import streamlit as st

from camposync.agente import perguntar_detalhado  # carrega o .env como efeito colateral
from ui import estado, tema

AVATAR_USUARIO, AVATAR_AGENTE = "🧑‍🌾", "🌾"

# Nome da ferramenta MCP -> (ícone, descrição amigável)
FERRAMENTAS = {
    "listar_fazendas": ("🏡", "Consultou o cadastro de fazendas"),
    "gastos_por_safra": ("💸", "Somou os gastos da safra"),
    "comparar_safras": ("⚖️", "Comparou duas safras"),
    "resultado_safra": ("📈", "Calculou receita, despesa e margem"),
    "cotacao_atual": ("🌾", "Buscou a cotação atual"),
    "historico_cotacoes": ("📉", "Consultou o histórico de preços"),
    "detectar_anomalias": ("🚨", "Procurou gastos fora do padrão"),
    "buscar_lancamentos": ("🧾", "Consultou lançamentos individuais"),
    "recomendar_acoes": ("💡", "Gerou recomendações"),
    "detectar_duplicados": ("👯", "Procurou lançamentos duplicados"),
    "buscar_documentos": ("📚", "Pesquisou na base de conhecimento (RAG)"),
}

SUGESTOES = [
    ("💸", "Qual foi o gasto total na safra 2024/25?"),
    ("🔎", "Por que minha safra 2025/26 custou mais que a anterior?"),
    ("📈", "Qual a margem bruta da safra 2023/24?"),
    ("🚨", "Tem algum gasto fora do normal nas minhas fazendas?"),
    ("👯", "Tem algum lançamento duplicado?"),
    ("🌾", "Qual a cotação da soja hoje? Compensa vender agora?"),
    ("📚", "O que é o LCDPR e preciso declarar?"),
]


def _rotulo(nome: str):
    return FERRAMENTAS.get(nome, ("🔧", nome))


def _resumo_args(args: dict) -> str:
    itens = [f"{k}={v}" for k, v in args.items() if k != "fazenda_id" and v not in (None, "")]
    return ", ".join(itens)


def _mostrar_meta(meta: dict):
    """Expander 'como cheguei nessa resposta' com ferramentas e fontes."""
    ferr, fontes = meta.get("ferramentas", []), meta.get("fontes", [])
    if not ferr:
        st.caption("Respondeu sem consultar dados ou documentos.")
        return
    titulo = f"🔎 Como cheguei nessa resposta · {len(ferr)} consulta{'s' if len(ferr) > 1 else ''}"
    with st.expander(titulo):
        passos = ""
        for f in ferr:
            ic, desc = _rotulo(f["nome"])
            detalhe = _resumo_args(f["args"])
            passos += (
                f'<div class="passo-ferr"><div class="ic">{ic}</div><div>'
                f'<div class="t">{tema.esc(desc)}</div>'
                f'<div class="d">{tema.esc(f["nome"])}({tema.esc(detalhe)}) · {f["segundos"]}s</div></div></div>'
            )
        st.markdown(passos, unsafe_allow_html=True)
        if fontes:
            st.markdown("**Fontes consultadas**")
            vistos = set()
            for fo in fontes:
                chave = (fo["fonte"], fo.get("pagina"))
                if chave in vistos:
                    continue
                vistos.add(chave)
                pag = f" · p. {fo['pagina']}" if fo.get("pagina") != "" and fo.get("pagina") is not None else ""
                trecho = fo["texto"].strip().replace("\n", " ")[:220]
                st.markdown(
                    f'<div class="fonte"><div class="f">📄 {tema.esc(fo["fonte"])}{tema.esc(pag)}</div>'
                    f'<div class="x">“{tema.esc(trecho)}…”</div></div>',
                    unsafe_allow_html=True,
                )
        if meta.get("modelo"):
            st.caption(f"Modelo: {meta['modelo']}")


def _historico_para_agente(chat: list[dict]) -> list[dict]:
    return [{"role": m["role"], "content": m["agente"]} for m in chat]


def render(fazenda: dict):
    chave = f"chat_{fazenda['id']}"
    chat = st.session_state.setdefault(chave, [])

    topo, limpar = st.columns([5, 1])
    with topo:
        tema.cabecalho("Consultor da Safra", f"Pergunte em linguagem natural sobre a {fazenda['nome']}.")
    with limpar:
        if chat and st.button("🗑️ Nova conversa", use_container_width=True):
            st.session_state[chave] = []
            st.rerun()

    if not os.environ.get("OPENROUTER_API_KEY"):
        st.warning("`OPENROUTER_API_KEY` não encontrada. Crie um arquivo `.env` (veja `.env.example`) para o agente responder.")

    pergunta = st.chat_input("Faça uma pergunta sobre sua fazenda…") or st.session_state.pop("pergunta_pendente", None)

    # Tela inicial com sugestões
    if not chat and not pergunta:
        st.markdown(
            '<div class="hero"><div class="em">🌾</div><h2>Como posso ajudar na safra?</h2>'
            '<p>Eu cruzo os lançamentos da sua fazenda com a base técnica da Embrapa e da Conab '
            'para explicar custos, margens e preços.</p></div>',
            unsafe_allow_html=True,
        )
        st.write("")
        cols = st.columns(2)
        for i, (ic, texto) in enumerate(SUGESTOES):
            cols[i % 2].button(f"{ic}  {texto}", key=f"sug_{i}", use_container_width=True,
                               on_click=estado.perguntar_ao_consultor, args=(texto,))

    # Histórico
    for m in chat:
        with st.chat_message(m["role"], avatar=AVATAR_USUARIO if m["role"] == "user" else AVATAR_AGENTE):
            st.markdown(m["texto"])
            if m["role"] == "assistant" and m.get("meta"):
                _mostrar_meta(m["meta"])

    # Nova pergunta
    if pergunta:
        contexto = f"[Fazenda selecionada: {fazenda['nome']} (id={fazenda['id']})] {pergunta}"
        chat.append({"role": "user", "texto": pergunta, "agente": contexto})
        with st.chat_message("user", avatar=AVATAR_USUARIO):
            st.markdown(pergunta)

        with st.chat_message("assistant", avatar=AVATAR_AGENTE):
            status = st.status("Consultando os dados da fazenda…", expanded=True)

            def ao_chamar(nome, args):
                ic, desc = _rotulo(nome)
                status.write(f"{ic} {desc}…")

            try:
                r = perguntar_detalhado(_historico_para_agente(chat), ao_chamar)
                status.update(label="Pronto", state="complete", expanded=False)
                chat.append({
                    "role": "assistant", "texto": r["resposta"], "agente": r["resposta"],
                    "meta": {k: r[k] for k in ("ferramentas", "fontes", "modelo")},
                })
            except Exception as e:  # noqa: BLE001 - mostramos o erro ao usuário em vez de quebrar a página
                status.update(label="Não consegui responder", state="error", expanded=False)
                chat.pop()  # remove a pergunta sem resposta para não poluir o contexto
                st.error(f"Erro ao consultar o modelo: {e}")
                st.stop()
        st.rerun()
