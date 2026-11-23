"""Identidade visual do Consultor da Safra: paleta, CSS e componentes HTML."""
import html
import streamlit as st

VERDE = "#1F6B43"
VERDE_ESCURO = "#14452C"
VERDE_CLARO = "#E3EFE6"
OURO = "#C98A1B"
TERRA = "#8B5E3C"
VERMELHO = "#B3412F"
FUNDO = "#F7F5EF"
TEXTO = "#1F2A24"
MUDO = "#6B756E"
BORDA = "#E4E0D3"

# Paleta categórica para os gráficos (9 categorias de custo)
SERIE = ["#1F6B43", "#C98A1B", "#8B5E3C", "#2F6F8F", "#7A8F3B",
         "#8E3B46", "#6C7A89", "#D1763A", "#B8A67D"]

# O CSS usa tokens __NOME__ (trocados abaixo) para não conflitar com as chaves do CSS.
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"], .stMarkdown, button, input, textarea {
    font-family: 'Inter', system-ui, sans-serif;
}
h1, h2, h3 { font-family: 'Fraunces', Georgia, serif; color: __VERDE_ESCURO__; letter-spacing: -0.01em; }

/* Limpa elementos padrão do Streamlit */
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"] { visibility: hidden; height: 0; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 5rem; max-width: 1180px; }

/* Sidebar */
[data-testid="stSidebar"] { background: __FUNDO__; border-right: 1px solid __BORDA__; }
.marca {
    background: linear-gradient(135deg, __VERDE_ESCURO__, __VERDE__);
    border-radius: 16px; padding: 18px 18px 16px; color: #fff; margin-bottom: 14px;
}
.marca .logo { font-size: 1.9rem; line-height: 1; }
.marca .nome { font-family: 'Fraunces', serif; font-size: 1.35rem; font-weight: 700; margin-top: 6px; }
.marca .sub { font-size: .78rem; opacity: .8; margin-top: 2px; }
.rotulo { font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; color: __MUDO__; font-weight: 600; margin: 14px 0 6px; }

/* Navegação (st.radio estilizado como menu) */
[data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; }
[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: 9px 12px; border-radius: 10px; width: 100%; cursor: pointer; transition: background .15s;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: __VERDE_CLARO__; }
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child { display: none; }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: __VERDE_CLARO__; }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: __VERDE_ESCURO__; font-weight: 600; }

.ficha { background: #fff; border: 1px solid __BORDA__; border-radius: 12px; padding: 12px 14px; font-size: .85rem; line-height: 1.7; }
.ficha b { color: __VERDE_ESCURO__; }

/* Cabeçalho de página */
.pagina-titulo { font-family: 'Fraunces', serif; font-size: 2rem; font-weight: 700; color: __VERDE_ESCURO__; margin: 0; }
.pagina-sub { color: __MUDO__; margin: 2px 0 18px; font-size: .98rem; }

/* Cartões de métrica */
.kpi {
    background: #fff; border: 1px solid __BORDA__; border-radius: 16px; padding: 16px 18px;
    box-shadow: 0 1px 2px rgba(31,42,36,.04); height: 100%;
}
.kpi .rot { font-size: .75rem; text-transform: uppercase; letter-spacing: .07em; color: __MUDO__; font-weight: 600; }
.kpi .val { font-family: 'Fraunces', serif; font-size: 1.75rem; font-weight: 700; color: __TEXTO__; margin: 4px 0 2px; }
.kpi .var { font-size: .82rem; font-weight: 500; }
.kpi .var.bom { color: __VERDE__; } .kpi .var.ruim { color: __VERMELHO__; } .kpi .var.neutro { color: __MUDO__; }
.kpi.destaque { background: linear-gradient(135deg, __VERDE_ESCURO__, __VERDE__); border: 0; }
.kpi.destaque .rot { color: #cfe5d6; } .kpi.destaque .val { color: #fff; }
.kpi.destaque .var { color: #cfe5d6 !important; }

.secao { font-family: 'Fraunces', serif; font-size: 1.2rem; font-weight: 700; color: __VERDE_ESCURO__; margin: 26px 0 4px; }
.secao-sub { color: __MUDO__; font-size: .88rem; margin-bottom: 8px; }

/* Alertas e recomendações */
.alerta {
    background: #fff; border: 1px solid __BORDA__; border-left: 5px solid __OURO__;
    border-radius: 12px; padding: 12px 14px; margin-bottom: 8px;
}
.alerta.alta { border-left-color: __VERMELHO__; } .alerta.media { border-left-color: __OURO__; } .alerta.baixa { border-left-color: __VERDE__; }
.alerta .tit { font-weight: 600; color: __TEXTO__; font-size: .95rem; }
.alerta .txt { color: #3b463f; font-size: .9rem; margin-top: 4px; line-height: 1.5; }
.selo {
    display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: .7rem; font-weight: 600;
    background: __VERDE_CLARO__; color: __VERDE_ESCURO__; margin-right: 6px;
}
.selo.alta { background: #F6DDD7; color: __VERMELHO__; } .selo.media { background: #F8EBCF; color: #8a5d0b; }

/* Passos (importação) */
.passos { display: flex; gap: 10px; margin: 6px 0 18px; }
.passo { flex: 1; background: #fff; border: 1px solid __BORDA__; border-radius: 12px; padding: 10px 14px; color: __MUDO__; font-size: .88rem; }
.passo b { display: inline-flex; width: 24px; height: 24px; border-radius: 50%; background: __BORDA__; color: __MUDO__;
    align-items: center; justify-content: center; margin-right: 8px; font-size: .8rem; }
.passo.ativo { border-color: __VERDE__; color: __VERDE_ESCURO__; font-weight: 600; }
.passo.ativo b, .passo.feito b { background: __VERDE__; color: #fff; }
.passo.feito { color: __VERDE_ESCURO__; }

/* Chat */
[data-testid="stChatMessage"] { background: transparent; border-radius: 14px; padding: .6rem .4rem; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: __VERDE_CLARO__; }
.passo-ferr { display: flex; gap: 10px; align-items: flex-start; padding: 6px 0; border-bottom: 1px dashed __BORDA__; font-size: .88rem; }
.passo-ferr:last-child { border-bottom: 0; }
.passo-ferr .ic { font-size: 1.1rem; }
.passo-ferr .t { font-weight: 600; color: __TEXTO__; } .passo-ferr .d { color: __MUDO__; font-size: .8rem; }
.fonte { background: #fff; border: 1px solid __BORDA__; border-radius: 10px; padding: 8px 12px; margin: 6px 0; font-size: .84rem; }
.fonte .f { font-weight: 600; color: __VERDE_ESCURO__; } .fonte .x { color: __MUDO__; margin-top: 3px; }

/* Hero do chat vazio */
.hero { text-align: center; padding: 28px 0 8px; }
.hero .em { font-size: 2.6rem; }
.hero h2 { margin: 6px 0 4px; } .hero p { color: __MUDO__; max-width: 560px; margin: 0 auto; }

/* Botões */
.stButton > button, .stDownloadButton > button {
    border-radius: 10px; border: 1px solid __BORDA__; font-weight: 500; transition: all .15s;
}
.stButton > button:hover { border-color: __VERDE__; color: __VERDE__; }
.stButton > button[kind="primary"] { background: __VERDE__; border-color: __VERDE__; color: #fff; }
.stButton > button[kind="primary"]:hover { background: __VERDE_ESCURO__; color: #fff; }

/* Uploader */
[data-testid="stFileUploaderDropzone"] { background: #fff; border: 2px dashed __VERDE__; border-radius: 16px; padding: 28px; }
</style>
"""


def _css() -> str:
    css = _CSS
    for nome in ("VERDE_ESCURO", "VERDE_CLARO", "VERDE", "OURO", "VERMELHO", "FUNDO", "TEXTO", "MUDO", "BORDA"):
        css = css.replace(f"__{nome}__", globals()[nome])
    return css


def aplicar_tema():
    st.markdown(_css(), unsafe_allow_html=True)


def esc(texto) -> str:
    return html.escape(str(texto))


def brl(valor, casas=0) -> str:
    """Formata em reais no padrão brasileiro: R$ 1.234.567."""
    if valor is None:
        return "—"
    s = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def cabecalho(titulo: str, subtitulo: str = ""):
    st.markdown(f'<h1 class="pagina-titulo">{esc(titulo)}</h1>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<p class="pagina-sub">{esc(subtitulo)}</p>', unsafe_allow_html=True)


def secao(titulo: str, subtitulo: str = ""):
    st.markdown(f'<div class="secao">{esc(titulo)}</div>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<div class="secao-sub">{esc(subtitulo)}</div>', unsafe_allow_html=True)


def kpi(rotulo: str, valor: str, variacao: str = "", tom: str = "neutro", destaque: bool = False):
    """Cartão de métrica. tom: bom | ruim | neutro (cor da variação)."""
    classe = "kpi destaque" if destaque else "kpi"
    var = f'<div class="var {tom}">{esc(variacao)}</div>' if variacao else ""
    st.markdown(
        f'<div class="{classe}"><div class="rot">{esc(rotulo)}</div>'
        f'<div class="val">{esc(valor)}</div>{var}</div>',
        unsafe_allow_html=True,
    )


def layout_grafico(fig, altura=340):
    """Aplica o visual padrão a um gráfico Plotly."""
    fig.update_layout(
        height=altura, margin=dict(l=8, r=8, t=30, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=TEXTO, size=12),
        colorway=SERIE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        hoverlabel=dict(bgcolor="#fff", font_size=12),
    )
    fig.update_xaxes(showgrid=False, linecolor=BORDA)
    fig.update_yaxes(gridcolor="#ECE8DB", zeroline=False)
    return fig
