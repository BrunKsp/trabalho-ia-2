"""
Consultor da Safra — ponto de entrada da interface.
Uso: streamlit run app.py

A interface mora em ui/ (tema, dados e uma página por arquivo);
a inteligência (agente, MCP, RAG) mora em camposync/.
"""
import streamlit as st

st.set_page_config(page_title="Consultor da Safra", page_icon="🌾", layout="wide")

from ui import dados, estado, tema  # noqa: E402 - depois do set_page_config
from ui.paginas import consultor, importar, painel, recomendacoes  # noqa: E402

tema.aplicar_tema()

PAGINAS = {
    estado.PAINEL: painel,
    estado.CONSULTOR: consultor,
    estado.IMPORTAR: importar,
    estado.RECOMENDACOES: recomendacoes,
}

with st.sidebar:
    st.markdown(
        '<div class="marca"><div class="logo">🌾</div><div class="nome">Consultor da Safra</div>'
        '<div class="sub">CampoSync · IA para o produtor rural</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="rotulo">Fazenda</div>', unsafe_allow_html=True)
    lista = dados.fazendas()
    por_nome = {f["nome"]: f for f in lista}
    nome = st.selectbox("Fazenda ativa", list(por_nome), label_visibility="collapsed")
    fazenda = por_nome[nome]
    st.markdown(
        f'<div class="ficha"><b>📍</b> {tema.esc(fazenda["municipio"])}<br>'
        f'<b>📐</b> {fazenda["area_ha"]} ha<br>'
        f'<b>🌱</b> {tema.esc(fazenda["culturas"].replace(",", ", "))}<br>'
        f'<b>🧾</b> {dados.total_lancamentos(fazenda["id"])} lançamentos</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="rotulo">Navegação</div>', unsafe_allow_html=True)
    st.radio("Página", estado.PAGINAS, key="pagina", label_visibility="collapsed")

    st.markdown('<div class="rotulo">Sobre</div>', unsafe_allow_html=True)
    st.caption("Dados financeiros sintéticos, calibrados pela estrutura de custos da Conab. "
               "Base técnica: Embrapa, Conab e artigos acadêmicos.")

PAGINAS[st.session_state["pagina"]].render(fazenda)
