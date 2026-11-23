"""Recomendações proativas geradas a partir do histórico da fazenda."""
import streamlit as st

from ui import dados, estado, tema

TIPOS = {  # tipo -> (ícone Material, título)
    "alerta_custo": ("payments", "Alerta de custo"),
    "alerta_margem": ("trending_down", "Alerta de margem"),
    "benchmark_interno": ("workspace_premium", "Sua melhor safra"),
    "sazonalidade": ("calendar_month", "Planejamento sazonal"),
}
PRIORIDADES = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}


def render(fazenda: dict):
    fid = fazenda["id"]
    tema.cabecalho("Recomendações", f"O que o histórico da {fazenda['nome']} sugere fazer agora", "lightbulb")

    recs = dados.recomendacoes(fid)
    if not recs:
        tema.aviso("Ainda não há histórico suficiente para recomendar ações.", "", "info")
        return

    contagem = {p: sum(1 for r in recs if r["prioridade"] == p) for p in PRIORIDADES}
    tema.mostrar_campos([
        {"rotulo": "Prioridade alta", "valor": str(contagem["alta"]), "estado": "ruim" if contagem["alta"] else None,
         "sub": "pedem atenção agora"},
        {"rotulo": "Prioridade média", "valor": str(contagem["media"]), "sub": "vale acompanhar"},
        {"rotulo": "Planejamento", "valor": str(contagem["baixa"]), "sub": "para o calendário da safra"},
    ], kpi=True)
    st.write("")
    filtro = st.segmented_control("Mostrar", ["Todas", "Alta", "Média", "Baixa"], default="Todas",
                                  label_visibility="collapsed", key=f"filtro_rec_{fid}") or "Todas"
    escolhida = {"Alta": "alta", "Média": "media", "Baixa": "baixa"}.get(filtro)

    for i, r in enumerate(recs):
        if escolhida and r["prioridade"] != escolhida:
            continue
        ic, titulo = TIPOS.get(r["tipo"], ("lightbulb", r["tipo"]))
        extra = r.get("categoria") or r.get("cultura")
        with st.container(key=f"linha_rec_{i}"):
            col_txt, col_btn = st.columns([5, 1.2], vertical_alignment="top")
            with col_txt:
                st.markdown(
                    f'<div class="item {r["prioridade"]}">{tema.ms(ic)}<div>'
                    f'<div class="tit">{tema.esc(titulo)}'
                    f'{(" · " + tema.esc(dados.nome_categoria(extra))) if extra else ""}'
                    f'<span class="prio {r["prioridade"]}">Prioridade {PRIORIDADES[r["prioridade"]].lower()}</span></div>'
                    f'<div class="txt">{tema.esc(r["mensagem"])}</div></div></div>'
                    + (tema.campos([{"rotulo": c["rotulo"], "valor": c["valor"]} for c in r.get("campos", [])])
                       if r.get("campos") else ""),
                    unsafe_allow_html=True,
                )
            with col_btn:
                st.button("Aprofundar", key=f"rec_{fid}_{i}", icon=":material/forum:", type="tertiary",
                      on_click=estado.perguntar_ao_consultor,
                      args=(f"Quero entender melhor esta recomendação e o que fazer na prática: {r['mensagem']}",))
