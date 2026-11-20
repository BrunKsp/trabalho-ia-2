"""
Interface Streamlit — Consultor da Safra
Uso: streamlit run app.py
"""
import streamlit as st
import json
from agente import perguntar, executar_ferramenta, TOOLS, SYSTEM
from servidor_mcp import listar_fazendas

st.set_page_config(page_title="Consultor da Safra", page_icon="🌾", layout="wide")

# ── Sidebar: seleção de fazenda ──────────────────────────────────────────────
with st.sidebar:
    st.title("🌾 Consultor da Safra")
    st.caption("CampoSync · Demo Trabalho IA II")
    st.divider()

    fazendas = listar_fazendas()
    opcoes = {f["nome"]: f["id"] for f in fazendas}
    fazenda_nome = st.selectbox("Fazenda ativa", list(opcoes.keys()))
    fazenda_id = opcoes[fazenda_nome]

    faz_info = next(f for f in fazendas if f["id"] == fazenda_id)
    st.markdown(f"**Município:** {faz_info['municipio']}")
    st.markdown(f"**Área:** {faz_info['area_ha']} ha")
    st.markdown(f"**Culturas:** {faz_info['culturas']}")

    st.divider()
    st.markdown("**Perguntas de exemplo:**")
    exemplos = [
        "Qual foi o gasto total na safra 2024/25?",
        "Por que minha safra de soja 2025/26 custou mais?",
        "Qual a margem da safra 2023/24?",
        "Tem alguma anomalia nos meus gastos?",
        "Qual a cotação da soja hoje?",
        "O que é o LCDPR e preciso fazer?",
    ]
    for ex in exemplos:
        if st.button(ex, use_container_width=True):
            st.session_state.pergunta_rapida = ex

    if st.button("🗑️ Limpar conversa", use_container_width=True):
        st.session_state.historico = []
        st.rerun()

# ── Chat principal ───────────────────────────────────────────────────────────
st.header("Consultor da Safra")

if "historico" not in st.session_state:
    st.session_state.historico = []

# Renderiza histórico
for msg in st.session_state.historico:
    role = "user" if msg["role"] == "user" else "assistant"
    with st.chat_message(role):
        content = msg["content"]
        if isinstance(content, str):
            st.markdown(content)
        elif isinstance(content, list):
            text_parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
            for b in content:
                if hasattr(b, "type") and b.type == "text" and b.text not in text_parts:
                    text_parts.append(b.text)
            if text_parts:
                st.markdown("\n\n".join(text_parts))

# Input do usuário
pergunta = st.chat_input("Faça uma pergunta sobre sua fazenda...")

# Botão de pergunta rápida sobrepõe o chat_input
if "pergunta_rapida" in st.session_state:
    pergunta = st.session_state.pop("pergunta_rapida")

if pergunta:
    # Injeta contexto da fazenda selecionada na pergunta
    pergunta_contextualizada = f"[Fazenda selecionada: {fazenda_nome} (id={fazenda_id})] {pergunta}"

    with st.chat_message("user"):
        st.markdown(pergunta)

    st.session_state.historico.append({"role": "user", "content": pergunta_contextualizada})

    with st.chat_message("assistant"):
        with st.spinner("Consultando dados..."):
            try:
                resposta = perguntar(list(st.session_state.historico))
            except Exception as e:
                resposta = f"⚠️ Erro ao consultar o modelo: {e}"
        st.markdown(resposta)

    st.session_state.historico.append({"role": "assistant", "content": resposta})
    st.rerun()
