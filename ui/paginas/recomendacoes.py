"""Recomendações proativas geradas a partir do histórico da fazenda."""
import streamlit as st

from ui import dados, estado, tema

TIPOS = {
    "alerta_custo": ("💸", "Alerta de custo"),
    "alerta_margem": ("📉", "Alerta de margem"),
    "benchmark_interno": ("🏆", "Sua melhor safra"),
    "sazonalidade": ("🗓️", "Planejamento sazonal"),
}
PRIORIDADES = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}


def render(fazenda: dict):
    fid = fazenda["id"]
    tema.cabecalho("Recomendações", f"O que o histórico da {fazenda['nome']} sugere fazer agora.")

    recs = dados.recomendacoes(fid)
    if not recs:
        st.info("Ainda não há histórico suficiente para recomendar ações.")
        return

    contagem = {p: sum(1 for r in recs if r["prioridade"] == p) for p in PRIORIDADES}
    c1, c2, c3 = st.columns(3)
    with c1:
        tema.kpi("Prioridade alta", str(contagem["alta"]), "pedem atenção agora", "ruim" if contagem["alta"] else "neutro")
    with c2:
        tema.kpi("Prioridade média", str(contagem["media"]), "vale acompanhar")
    with c3:
        tema.kpi("Planejamento", str(contagem["baixa"]), "para o calendário da safra")

    filtro = st.radio("Mostrar", ["Todas", "Alta", "Média", "Baixa"], horizontal=True, label_visibility="collapsed")
    escolhida = {"Alta": "alta", "Média": "media", "Baixa": "baixa"}.get(filtro)

    for i, r in enumerate(recs):
        if escolhida and r["prioridade"] != escolhida:
            continue
        ic, titulo = TIPOS.get(r["tipo"], ("💡", r["tipo"]))
        extra = r.get("categoria") or r.get("cultura")
        col_txt, col_btn = st.columns([5, 1.4])
        with col_txt:
            st.markdown(
                f'<div class="alerta {r["prioridade"]}"><div class="tit">{ic} {tema.esc(titulo)} '
                f'<span class="selo {r["prioridade"]}">{PRIORIDADES[r["prioridade"]]}</span>'
                f'{f"<span class=selo>{tema.esc(dados.nome_categoria(extra))}</span>" if extra else ""}</div>'
                f'<div class="txt">{tema.esc(r["mensagem"])}</div></div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            st.button("💬 Aprofundar", key=f"rec_{fid}_{i}", use_container_width=True,
                      on_click=estado.perguntar_ao_consultor,
                      args=(f"Quero entender melhor esta recomendação e o que fazer na prática: {r['mensagem']}",))
