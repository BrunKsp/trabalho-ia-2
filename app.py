"""
Interface Streamlit — Consultor da Safra
Uso: streamlit run app.py
"""
import streamlit as st
import json
import tempfile, os
from pathlib import Path
from agente import perguntar, executar_ferramenta, TOOLS, SYSTEM
from servidor_mcp import listar_fazendas, recomendar_acoes

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
        "O que você recomenda para melhorar meus resultados?",
    ]
    for ex in exemplos:
        if st.button(ex, use_container_width=True):
            st.session_state.pergunta_rapida = ex

    if st.button("🗑️ Limpar conversa", use_container_width=True):
        st.session_state.historico = []
        st.rerun()

# ── Abas principais ──────────────────────────────────────────────────────────
tab_chat, tab_upload, tab_recomendacoes = st.tabs(["💬 Consultor", "📂 Importar Dados", "💡 Recomendações"])

# ════════════════════════════════════════════════════════════════════════════
# ABA 1 — CHAT
# ════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.header("Consultor da Safra")

    if "historico" not in st.session_state:
        st.session_state.historico = []

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

    pergunta = st.chat_input("Faça uma pergunta sobre sua fazenda...")

    if "pergunta_rapida" in st.session_state:
        pergunta = st.session_state.pop("pergunta_rapida")

    if pergunta:
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

# ════════════════════════════════════════════════════════════════════════════
# ABA 2 — UPLOAD DE DOCUMENTOS
# ════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.header("Importar Dados Financeiros")
    st.markdown(
        "Suba **notas fiscais, boletos, extratos ou planilhas** da fazenda. "
        "O sistema extrai os lançamentos automaticamente e importa para o histórico."
    )

    arquivo = st.file_uploader(
        "Selecione o arquivo",
        type=["pdf", "csv", "xlsx", "xls"],
        help="PDF de nota fiscal / boleto, planilha CSV ou Excel com lançamentos",
    )

    if arquivo:
        ext = Path(arquivo.name).suffix.lower()
        st.info(f"Arquivo: **{arquivo.name}** ({ext})")

        if st.button("🔍 Extrair lançamentos", type="primary"):
            from parser_documentos import (
                extrair_lancamentos_pdf,
                extrair_lancamentos_csv,
                extrair_lancamentos_excel,
            )

            with st.spinner("Analisando documento..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(arquivo.read())
                    tmp_path = tmp.name

                try:
                    if ext == ".pdf":
                        lancamentos = extrair_lancamentos_pdf(tmp_path)
                    elif ext == ".csv":
                        lancamentos = extrair_lancamentos_csv(tmp_path)
                    else:
                        lancamentos = extrair_lancamentos_excel(tmp_path)
                finally:
                    os.unlink(tmp_path)

            if not lancamentos:
                st.warning("Nenhum lançamento encontrado. Verifique se o arquivo contém dados financeiros estruturados.")
            else:
                st.success(f"**{len(lancamentos)} lançamentos encontrados.** Revise abaixo antes de confirmar:")
                import pandas as pd
                df_preview = pd.DataFrame(lancamentos)
                st.dataframe(df_preview, use_container_width=True)

                st.session_state.lancamentos_pendentes = lancamentos

        if "lancamentos_pendentes" in st.session_state and st.session_state.lancamentos_pendentes:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirmar importação", type="primary"):
                    from parser_documentos import importar_lancamentos
                    n = importar_lancamentos(st.session_state.lancamentos_pendentes, fazenda_id)
                    st.session_state.lancamentos_pendentes = []
                    st.success(f"**{n} lançamentos importados** com sucesso para {fazenda_nome}!")
                    st.rerun()
            with col2:
                if st.button("❌ Cancelar"):
                    st.session_state.lancamentos_pendentes = []
                    st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# ABA 3 — RECOMENDAÇÕES
# ════════════════════════════════════════════════════════════════════════════
with tab_recomendacoes:
    st.header("Recomendações para sua Fazenda")
    st.markdown(
        f"Análise do histórico da **{fazenda_nome}** com recomendações práticas "
        "baseadas nos padrões das suas safras anteriores."
    )

    if st.button("🔄 Gerar recomendações", type="primary"):
        with st.spinner("Analisando histórico..."):
            try:
                recs = recomendar_acoes(fazenda_id)
                st.session_state.recomendacoes = recs
            except Exception as e:
                st.error(f"Erro ao gerar recomendações: {e}")

    recs = st.session_state.get("recomendacoes", [])

    if recs:
        cores = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}
        tipos = {
            "alerta_custo": "Alerta de Custo",
            "alerta_margem": "Alerta de Margem",
            "benchmark_interno": "Benchmark Interno",
            "sazonalidade": "Planejamento Sazonal",
        }

        for rec in recs:
            icone = cores.get(rec.get("prioridade", "baixa"), "⚪")
            titulo = tipos.get(rec.get("tipo", ""), rec.get("tipo", ""))
            with st.expander(f"{icone} {titulo}", expanded=rec.get("prioridade") == "alta"):
                st.markdown(rec["mensagem"])
                if "categoria" in rec:
                    st.caption(f"Categoria: {rec['categoria']}")
    elif "recomendacoes" in st.session_state:
        st.info("Nenhuma recomendação gerada. Pode ser que não haja histórico suficiente.")
