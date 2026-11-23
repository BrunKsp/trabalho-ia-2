"""Estado compartilhado entre páginas e navegação."""
import streamlit as st

PAGINAS = ["📊  Painel", "💬  Consultor", "📂  Importar dados", "💡  Recomendações"]
PAINEL, CONSULTOR, IMPORTAR, RECOMENDACOES = PAGINAS


def ir_para(pagina: str):
    """Troca de página. Use dentro de um on_click (antes do rerun) para não conflitar com o widget."""
    st.session_state["pagina"] = pagina


def perguntar_ao_consultor(pergunta: str):
    """Leva o usuário ao chat já com a pergunta enfileirada."""
    st.session_state["pergunta_pendente"] = pergunta
    ir_para(CONSULTOR)
