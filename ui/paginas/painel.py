"""Painel: visão geral da safra com métricas, gráficos e alertas."""
import plotly.graph_objects as go
import streamlit as st

from ui import dados, estado, tema


def _variacao(atual, anterior, mais_e_melhor=True):
    """(texto, tom, ícone) da variação percentual vs safra anterior."""
    if not anterior:
        return "", None, None
    pct = (atual - anterior) / abs(anterior) * 100
    bom = (pct >= 0) == mais_e_melhor
    icone = "arrow_upward" if pct >= 0 else "arrow_downward"
    return f"{abs(pct):.1f}% vs safra anterior".replace(".", ","), ("bom" if bom else "ruim"), icone


def _campo(rotulo, valor, atual, anterior, mais_e_melhor=True):
    txt, tom, ic = _variacao(atual, anterior, mais_e_melhor)
    return {"rotulo": rotulo, "valor": valor, "sub": txt or None, "sub_tom": tom, "sub_icone": ic}


def render(fazenda: dict):
    fid = fazenda["id"]
    tema.cabecalho(fazenda["nome"], f'{fazenda["municipio"]} · {fazenda["area_ha"]} ha · {fazenda["culturas"].replace(",", ", ")}')

    lista_safras = dados.safras(fid)
    lista_culturas = dados.culturas(fid)

    f1, f2, _ = st.columns([1, 1, 2])
    safra = f1.selectbox("Safra", lista_safras[::-1], key=f"safra_{fid}")
    cult_sel = f2.selectbox("Cultura", ["Todas"] + [c.capitalize() for c in lista_culturas], key=f"cult_{fid}")
    cultura = None if cult_sel == "Todas" else cult_sel.lower()

    res = dados.resultado(fid, safra, cultura)
    idx = lista_safras.index(safra)
    ant = dados.resultado(fid, lista_safras[idx - 1], cultura) if idx > 0 else None

    # ── Resultado da safra: uma faixa de campos da nota ─────────────────────
    pct = res["margem_pct"]
    prod = res["produtividade_sc_ha"]
    negativa = res["margem_bruta"] < 0
    tema.mostrar_campos([
        _campo("Receita bruta", tema.brl(res["receita_bruta"]), res["receita_bruta"], ant and ant["receita_bruta"]),
        _campo("Despesa total", tema.brl(res["despesa_total"]), res["despesa_total"], ant and ant["despesa_total"],
               mais_e_melhor=False),
        {"rotulo": "Margem bruta", "valor": tema.brl(res["margem_bruta"]),
         "estado": "foco ruim" if negativa else "foco",
         "sub": (f"{pct:.1f}% da receita".replace(".", ",") if pct is not None else "sem receita registrada"),
         "sub_tom": "ruim" if negativa else "bom"},
        _campo("Produtividade média", f"{prod:.1f} sc/ha".replace(".", ",") if prod else "—",
               prod or 0, ant and ant["produtividade_sc_ha"]),
    ], kpi=True)

    # ── Gráficos ────────────────────────────────────────────────────────────
    g1, g2 = st.columns(2)
    with g1:
        tema.secao("Para onde foi o dinheiro", f"Custos por categoria · safra {safra}")
        df = dados.custos_por_categoria(fid, safra, cultura)
        if df.empty:
            tema.aviso("Sem lançamentos para esta seleção.", "", "info")
        else:
            df = df.sort_values("total")
            fig = go.Figure(go.Bar(
                x=df["total"], y=df["categoria"], orientation="h",
                marker_color=tema.VERDE, text=[tema.brl(v) for v in df["total"]],
                textposition="outside", cliponaxis=False,
                hovertemplate="%{y}: %{text}<extra></extra>",
            ))
            fig.update_xaxes(visible=False, range=[0, df["total"].max() * 1.6])
            st.plotly_chart(tema.layout_grafico(fig, 360), use_container_width=True, config={"displayModeBar": False})

    with g2:
        tema.secao("Resultado por safra", "Receita, despesa e margem ao longo do tempo")
        ev = dados.evolucao(fid, cultura)
        fig = go.Figure()
        fig.add_bar(x=ev["safra"], y=ev["receita"], name="Receita", marker_color=tema.VERDE,
                    hovertemplate="Receita: R$ %{y:,.0f}<extra></extra>")
        fig.add_bar(x=ev["safra"], y=ev["despesa"], name="Despesa", marker_color="#8FA89A",
                    hovertemplate="Despesa: R$ %{y:,.0f}<extra></extra>")
        fig.add_scatter(x=ev["safra"], y=ev["margem"], name="Margem", mode="lines+markers",
                        line=dict(color=tema.TINTA, width=2.5),
                        hovertemplate="Margem: R$ %{y:,.0f}<extra></extra>")
        fig.update_layout(barmode="group")
        st.plotly_chart(tema.layout_grafico(fig, 360), use_container_width=True, config={"displayModeBar": False})

    # ── Cotação ─────────────────────────────────────────────────────────────
    tema.secao("Mercado", "Preço da saca (série sintética de demonstração)")
    padrao = cultura or lista_culturas[0]
    produtos = ["soja", "milho", "trigo"]
    produto = st.radio("Produto", produtos, index=produtos.index(padrao) if padrao in produtos else 0,
                       horizontal=True, label_visibility="collapsed", key=f"prod_{fid}")
    cot = dados.cotacoes(produto)
    atual, anterior = cot["preco_saca"].iloc[-1], cot["preco_saca"].iloc[-5]
    fig = go.Figure(go.Scatter(
        x=cot["data"], y=cot["preco_saca"], mode="lines", line=dict(color=tema.VERDE, width=2.5),
        fill="tozeroy", fillcolor="rgba(31,107,67,.08)",
        hovertemplate="%{x|%d/%m/%Y}<br>R$ %{y:.2f}/saca<extra></extra>",
    ))
    fig.update_yaxes(range=[cot["preco_saca"].min() * 0.9, cot["preco_saca"].max() * 1.05])
    st.plotly_chart(tema.layout_grafico(fig, 280), use_container_width=True, config={"displayModeBar": False})
    v, tom, _ = _variacao(atual, anterior)
    tema.mostrar_campos([
        {"rotulo": f"{produto.capitalize()} · preço da saca", "valor": f"R$ {atual:.2f}".replace(".", ","), "estado": "foco"},
        {"rotulo": "Data", "valor": f"{cot['data'].iloc[-1]:%d/%m/%Y}"},
        {"rotulo": "Em 4 semanas", "valor": ("+" if atual >= anterior else "−") + v.replace(" vs safra anterior", ""),
         "estado": None if tom == "bom" else "ruim"},
    ])

    # ── Alertas ─────────────────────────────────────────────────────────────
    tema.secao("Gastos fora do normal", "Categorias que fugiram mais de 20% da média histórica da fazenda")
    alertas = dados.anomalias(fid)[:4]
    if not alertas:
        tema.aviso("Nenhum gasto fora do padrão encontrado.", "ok", "check_circle")
    for i, a in enumerate(alertas):
        sinal = "+" if a["desvio_pct"] > 0 else ""
        cat = dados.nome_categoria(a["categoria"])
        nivel = "alta" if abs(a["desvio_pct"]) >= 25 else "media"
        with st.container(key=f"linha_alerta_{i}"):
            col_txt, col_btn = st.columns([5, 1.2], vertical_alignment="top")
        with col_txt:
            st.markdown(
                f'<div class="item {nivel}">{tema.ms("warning")}<div>'
                f'<div class="tit">{tema.esc(cat)} · {tema.esc(a["cultura"])} · safra {tema.esc(a["safra"])}</div></div></div>'
                + tema.campos([
                    {"rotulo": "Gasto", "valor": tema.brl(a["total"])},
                    {"rotulo": "Média da fazenda", "valor": tema.brl(a["media_historica"])},
                    {"rotulo": "Desvio", "valor": f"{sinal}{a['desvio_pct']:.0f}%", "estado": "alerta"},
                ]),
                unsafe_allow_html=True,
            )
        with col_btn:
            pergunta = f"Por que os gastos com {cat.lower()} em {a['cultura']} na safra {a['safra']} ficaram {abs(a['desvio_pct']):.0f}% {'acima' if a['desvio_pct'] > 0 else 'abaixo'} da média?"
            st.button("Investigar", key=f"inv_{fid}_{i}", icon=":material/search:", type="tertiary",
                      on_click=estado.perguntar_ao_consultor, args=(pergunta,))
