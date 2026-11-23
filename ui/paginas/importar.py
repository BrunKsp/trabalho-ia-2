"""Importar dados: upload de PDF/CSV/Excel -> revisão editável -> confirmação."""
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from camposync.parser_documentos import (
    CATEGORIAS_VALIDAS,
    extrair_lancamentos_csv,
    extrair_lancamentos_excel,
    extrair_lancamentos_pdf,
    importar_lancamentos,
)
from ui import dados, tema

MODELO_CSV = (
    "data,categoria,fornecedor,valor,cultura,safra\n"
    "2025-10-12,Fertilizantes,Coop. Agricola Regional,18500.00,soja,2025/26\n"
    "2025-10-20,Defensivos,Agro Insumos Sul,7200.50,soja,2025/26\n"
)


def _passos(ativo: int):
    nomes = ["Enviar arquivo", "Revisar lançamentos", "Importar"]
    html = '<div class="passos">'
    for i, nome in enumerate(nomes, 1):
        classe = "ativo" if i == ativo else ("feito" if i < ativo else "")
        marca = tema.ms("check") if i < ativo else i
        html += f'<div class="passo {classe}"><b>{marca}</b>{nome}</div>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


def _extrair(arquivo) -> list[dict]:
    ext = Path(arquivo.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(arquivo.getvalue())
        caminho = tmp.name
    try:
        if ext == ".pdf":
            return extrair_lancamentos_pdf(caminho)
        if ext == ".csv":
            return extrair_lancamentos_csv(caminho)
        return extrair_lancamentos_excel(caminho)
    finally:
        os.unlink(caminho)


def render(fazenda: dict):
    fid = fazenda["id"]
    tema.cabecalho("Importar dados", f"Notas fiscais, boletos ou planilhas para o histórico da {fazenda['nome']}", "upload_file")

    pendentes = st.session_state.get("lancamentos_pendentes")
    concluido = st.session_state.get("importacao_concluida")
    _passos(3 if concluido else (2 if pendentes else 1))

    if concluido:
        tema.aviso(f"{concluido} lançamentos importados para {fazenda['nome']}. Já aparecem no Painel e nas respostas do Consultor.",
                   "ok", "check_circle")
        if st.button("Importar outro arquivo", type="primary", icon=":material/upload_file:"):
            st.session_state.pop("importacao_concluida")
            st.rerun()
        return

    # ── Passo 2: revisão ────────────────────────────────────────────────────
    if pendentes:
        st.markdown(f"Encontrei **{len(pendentes)} lançamentos**. Corrija o que for preciso antes de importar — as células são editáveis.")
        df = pd.DataFrame(pendentes)
        colunas = [c for c in ["data", "categoria", "fornecedor", "valor", "cultura", "safra"] if c in df.columns]
        editado = st.data_editor(
            df[colunas], num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "valor": st.column_config.NumberColumn("valor (R$)", format="%.2f", min_value=0.0),
                "categoria": st.column_config.SelectboxColumn("categoria", options=CATEGORIAS_VALIDAS),
                "cultura": st.column_config.SelectboxColumn("cultura", options=["soja", "milho", "trigo"]),
            },
        )
        total = float(pd.to_numeric(editado["valor"], errors="coerce").fillna(0).sum()) if "valor" in editado else 0
        st.caption(f"{len(editado)} lançamentos · total {tema.brl(total, 2)}")

        c1, c2, _ = st.columns([1.3, 1, 3])
        if c1.button("Confirmar importação", type="primary", icon=":material/check:", use_container_width=True):
            registros = editado.dropna(subset=["valor"]).to_dict("records")
            n = importar_lancamentos(registros, fid)
            dados.limpar_cache()
            st.session_state.pop("lancamentos_pendentes", None)
            st.session_state["importacao_concluida"] = n
            st.rerun()
        if c2.button("Cancelar", use_container_width=True):
            st.session_state.pop("lancamentos_pendentes", None)
            st.rerun()
        tema.aviso("A importação grava os lançamentos no histórico da fazenda.", "", "info")
        return

    # ── Passo 1: envio ──────────────────────────────────────────────────────
    arquivo = st.file_uploader(
        "Arraste o arquivo aqui ou clique para escolher",
        type=["pdf", "csv", "xlsx", "xls"],
        help="PDF de nota fiscal ou boleto (lido por IA), ou planilha CSV/Excel com colunas data e valor.",
    )
    if arquivo:
        st.markdown(f'<div class="pagina-ctx">{tema.ms("attach_file")}<b>{tema.esc(arquivo.name)}</b>&nbsp;· '
                    f'{arquivo.size / 1024:.0f} KB</div>', unsafe_allow_html=True)
        if st.button("Extrair lançamentos", type="primary", icon=":material/document_scanner:"):
            with st.spinner("Lendo o documento…"):
                try:
                    lancamentos = _extrair(arquivo)
                except Exception as e:  # noqa: BLE001 - ex.: modelos ocupados, chave ausente
                    tema.aviso(f"Não consegui ler o documento agora: {e}", "erro", "error")
                    st.stop()
            if not lancamentos:
                tema.aviso("Não encontrei lançamentos nesse arquivo. Confira se a planilha tem colunas de data e valor, "
                           "ou se o PDF tem texto legível.", "", "search_off")
            else:
                st.session_state["lancamentos_pendentes"] = lancamentos
                st.rerun()

    st.download_button("Baixar planilha modelo (CSV)", MODELO_CSV, file_name="modelo_lancamentos.csv", mime="text/csv",
                       icon=":material/download:")
    with st.expander("Como funciona", icon=":material/help:"):
        st.markdown(
            "- **PDF** (nota fiscal, boleto): a IA lê o texto e extrai data, fornecedor, categoria e valor.\n"
            "- **CSV / Excel**: as colunas são reconhecidas pelo nome (`data`, `valor`, `categoria`, `fornecedor`, `cultura`, `safra`).\n"
            "- Você sempre revisa e edita antes de qualquer coisa ir para o histórico."
        )
