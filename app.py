"""
CampoSync · Consultor da Safra — ponto de entrada da interface.
Uso: streamlit run app.py

A interface mora em ui/ (tema, dados e uma página por arquivo);
a inteligência (agente, MCP, RAG) mora em camposync/.
"""
import streamlit as st

st.set_page_config(page_title="CampoSync · Consultor da Safra", page_icon=":material/agriculture:", layout="wide")

from ui import dados, estado, tema  # noqa: E402 - depois do set_page_config
from ui.paginas import consultor, importar, painel, recomendacoes  # noqa: E402

tema.aplicar_tema()

PAGINAS = {
    estado.PAINEL: painel,
    estado.CONSULTOR: consultor,
    estado.IMPORTAR: importar,
    estado.RECOMENDACOES: recomendacoes,
}

if st.session_state.get("pagina") not in PAGINAS:  # sessões antigas guardavam rótulos com emoji
    st.session_state["pagina"] = estado.PAINEL

with st.sidebar:
    st.markdown('<div class="marca"><b>CampoSync</b><span>Consultor da Safra</span></div>', unsafe_allow_html=True)

    # Fazenda ativa como campo da nota: seletor + ficha com município, área, culturas e lançamentos
    st.markdown('<div class="lab trilho-rotulo">Fazenda</div>', unsafe_allow_html=True)
    lista = dados.fazendas()
    por_nome = {f["nome"]: f for f in lista}
    nome = st.selectbox("Fazenda ativa", list(por_nome), label_visibility="collapsed")
    fazenda = por_nome[nome]
    st.markdown(
        '<div class="ficha">'
        f'<div class="cheia"><div class="lab">Município</div><div class="v">{tema.esc(fazenda["municipio"])}</div></div>'
        f'<div class="esq"><div class="lab">Área</div><div class="v">{fazenda["area_ha"]} ha</div></div>'
        f'<div><div class="lab">Lançamentos</div><div class="v">{dados.total_lancamentos(fazenda["id"])}</div></div>'
        f'<div class="cheia" style="border-top:1px solid rgba(255,255,255,.32);border-bottom:0">'
        f'<div class="lab">Culturas</div><div class="v">{tema.esc(fazenda["culturas"].replace(",", ", "))}</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    st.write("")
    st.radio("Página", estado.PAGINAS, key="pagina", format_func=estado.rotulo_menu, label_visibility="collapsed")

    st.markdown(
        f'<div class="nota-dados">{tema.ms("info")}<span>Dados financeiros sintéticos, calibrados pela estrutura '
        "de custos da Conab. Base técnica: Embrapa, Conab e artigos acadêmicos.</span></div>",
        unsafe_allow_html=True,
    )

PAGINAS[st.session_state["pagina"]].render(fazenda)
