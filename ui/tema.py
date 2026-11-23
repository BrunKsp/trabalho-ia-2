"""Identidade visual do CampoSync: tokens, CSS e componentes HTML.

Linguagem: a nota do produtor. Cada número mora num campo com rótulo pequeno
em maiúsculas e valor grande, com fios de 1px; estados mudam a cor do campo,
nunca o layout. Ícones: Material Symbols Rounded (a mesma família que o
Streamlit usa nos botões), nunca emoji.
"""
import html
import streamlit as st

# ── Tokens ───────────────────────────────────────────────────────────────────
VERDE = "#1F6B43"        # marca: trilho, ação primária, item ativo, campo em foco
VERDE_ESCURO = "#14452C"
VERDE_TINTA = "#EEF5F0"  # fundo da pergunta do produtor e seleção
BRANCO = "#FFFFFF"
SUPERFICIE = "#F4F6F5"   # segunda camada neutra (fundo de campos de entrada)
TINTA = "#17211B"
ROTULO = "#55605A"       # 6,6:1 sobre branco
FIO = "#D3DAD5"
AMBAR = "#8A5300"        # texto de alerta (5,9:1 sobre branco); borda usa AMBAR_FIO
AMBAR_FIO = "#D9A441"
AMBAR_FUNDO = "#FDF6E9"
VERMELHO = "#B3261E"
VERMELHO_FUNDO = "#FCEEEC"
VERDE_FIO = "#CFE0D5"     # borda da pergunta do produtor
OK_FIO = "#B9D3C3"        # borda do aviso de sucesso
ERRO_FIO = "#E9B4AE"      # borda do aviso de erro
GRADE = "#E9EDEA"         # linhas de grade dos gráficos

# Compatibilidade com nomes antigos usados nos gráficos
TEXTO, MUDO, BORDA, FUNDO = TINTA, ROTULO, FIO, BRANCO

# Séries dos gráficos: verde da marca, verde-acinzentado e tinta (restrito; cor de estado só onde há estado)
SERIE = ["#1F6B43", "#8FA89A", "#17211B", "#5C8A70", "#B8C7BE", "#3F5A4A", "#D3DAD5", "#2E7D57", "#6E7F75"]

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0..1,0&display=block');

/* ── Base ─────────────────────────────────────────────────────────────── */
html, body, .stApp, button, input, textarea, select,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"] {
    font-family: 'Public Sans', system-ui, sans-serif;
}
.stApp { background: __BRANCO__; color: __TINTA__; font-variant-numeric: tabular-nums; }
[data-testid="stIconMaterial"], .ms {
    font-family: 'Material Symbols Rounded' !important; font-weight: 400; font-style: normal;
    line-height: 1; letter-spacing: 0; text-transform: none; white-space: nowrap; direction: ltr;
    font-feature-settings: 'liga'; -webkit-font-smoothing: antialiased;
}
.ms { font-size: 20px; display: inline-block; vertical-align: -4px; }
h1, h2, h3, h4 { font-family: 'Public Sans', system-ui, sans-serif !important; color: __TINTA__; letter-spacing: -0.01em; }
[data-testid="stHeaderActionElements"] { display: none; }
::selection { background: __VERDE_TINTA__; color: __VERDE_ESCURO__; }
input, textarea { caret-color: __VERDE__; }
:focus-visible { outline: 2px solid __VERDE__; outline-offset: 2px; }
[data-testid="stCaptionContainer"] { opacity: 1; color: __ROTULO__; }
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"] { visibility: hidden; height: 0; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 6rem; max-width: 1120px; }

/* Rótulo de campo: a voz da nota */
.lab { font-size: 12px; line-height: 16px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: __ROTULO__; }

/* ── Trilho (sidebar) ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] { background: __VERDE__; border-right: 0; }
@media (min-width: 641px) {
    [data-testid="stSidebar"][data-collapsed="false"],
    [data-testid="stSidebar"][aria-expanded="true"] { width: 264px !important; min-width: 264px !important; max-width: 264px !important; }
}
[data-testid="stSidebar"] * { color: #fff; }
.marca { padding: 4px 4px 20px; }
.marca b { display: block; font-size: 20px; line-height: 24px; font-weight: 700; color: #fff; }
.marca span { font-size: 12px; line-height: 16px; font-weight: 500; color: rgba(255,255,255,.86); }
[data-testid="stSidebar"] .lab { color: rgba(255,255,255,.86); }
.trilho-rotulo { margin: 0 4px 6px; }
/* Seletor de fazenda: campo da nota sobre o verde */
/* Streamlit atual: combobox react-aria (div[role=group] > input + botão); versões antigas: baseweb */
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"],
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div {
    background: rgba(255,255,255,.08) !important; border: 1px solid rgba(255,255,255,.32) !important;
    border-radius: 8px 8px 0 0 !important; box-shadow: none !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] input,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] * {
    color: #fff !important; -webkit-text-fill-color: #fff; font-weight: 600; font-size: 15px; background: transparent !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] svg { fill: #fff; color: #fff; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] [data-testid="stIconMaterial"] { font-size: 20px; }
.ficha { display: grid; grid-template-columns: minmax(0, .8fr) minmax(0, 1.2fr); border: 1px solid rgba(255,255,255,.32); border-top: 0;
         border-radius: 0 0 8px 8px; margin-top: -1rem; }
.ficha > div { padding: 8px 10px; }
.ficha .lab { white-space: nowrap; }
.ficha .cheia { grid-column: 1 / 3; border-bottom: 1px solid rgba(255,255,255,.32); }
.ficha .esq { border-right: 1px solid rgba(255,255,255,.32); }
.ficha .v { white-space: nowrap; font-size: 15px; line-height: 22px; font-weight: 500; color: #fff; }
/* Navegação: st.radio como lista; item ativo é a pílula branca */
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stRadio"]),
[data-testid="stSidebar"] [data-testid="stRadio"], [data-testid="stSidebar"] [data-testid="stRadio"] > div,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] > div { width: 100% !important; }
[data-testid="stSidebar"] [data-testid="stRadioGroup"], [data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; width: 100%; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] {
    display: flex; width: 100%; align-self: stretch; box-sizing: border-box; min-height: 44px; align-items: center;
    padding: 0 16px; margin: 0; border-radius: 999px; cursor: pointer; transition: background .15s ease-out;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div { width: 100%; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:not([data-testid="stMarkdownContainer"]) { display: none; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] p { font-size: 15px; font-weight: 500; display: flex; align-items: center; gap: 12px; }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover { background: rgba(255,255,255,.12); }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) { background: #fff; }
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:checked) * { color: __VERDE__ !important; font-weight: 600; }
.nota-dados { display: flex; gap: 8px; margin: 28px 4px 0; font-size: 12px; line-height: 16px; color: rgba(255,255,255,.86); }
.nota-dados .ms { font-size: 16px; vertical-align: 0; }

/* ── Cabeçalho de página ──────────────────────────────────────────────── */
.pagina-titulo { font-size: 28px !important; line-height: 36px; font-weight: 700; color: __TINTA__; margin: 0; padding: 0; }
.pagina-ctx { display: flex; align-items: center; gap: 4px; color: __ROTULO__; font-size: 15px; margin: 4px 0 24px;
               padding-bottom: 16px; border-bottom: 1px solid __FIO__; }
.pagina-ctx .ms { font-size: 18px; vertical-align: 0; }
.secao { font-size: 20px; line-height: 28px; font-weight: 600; color: __TINTA__; margin: 32px 0 2px; }
.secao-sub { color: __ROTULO__; font-size: 15px; margin-bottom: 10px; }

/* ── Campos (a assinatura): fios de 1px pelo gap, valor grande, rótulo pequeno ── */
.campos { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px; background: __FIO__;
          border: 1px solid __FIO__; border-radius: 8px; overflow: hidden; margin: 12px 0 16px; }
.campos .f.largo { grid-column: span 2; }
.campos .f { background: #fff; padding: 8px 12px 12px; min-width: 0; }
.campos .v { font-size: 20px; line-height: 28px; font-weight: 600; margin-top: 4px; white-space: nowrap; color: __TINTA__; }
.campos .v.txt { white-space: normal; overflow-wrap: anywhere; }
.campos .v.txt { font-size: 15px; line-height: 24px; font-weight: 500; }
.campos .v .ms { color: __VERDE__; font-size: 18px; margin-right: 4px; vertical-align: -3px; }
.campos .s { font-size: 12px; line-height: 16px; color: __ROTULO__; margin-top: 4px; display: flex; align-items: center; gap: 2px; }
.campos .s .ms { font-size: 16px; vertical-align: 0; }
.campos .f.foco { box-shadow: inset 0 0 0 2px __VERDE__; }
.campos .f.alerta { background: __AMBAR_FUNDO__; } .campos .f.alerta .v { color: __AMBAR__; }
.campos .f.ruim .v, .campos .s.ruim { color: __VERMELHO__; }
.campos .s.bom { color: __VERDE__; }
.campos.kpi .v { font-size: 28px; line-height: 36px; }

/* Lista regrada (alertas e recomendações): fio de 1px entre linhas, prioridade só pela cor do texto */
[class*="st-key-linha_rec_"], [class*="st-key-linha_alerta_"] { border-top: 1px solid __FIO__; padding-top: 14px; }
[class*="st-key-linha_rec_"] .campos, [class*="st-key-linha_alerta_"] .campos { margin: 10px 0 8px 32px; }
.item { display: grid; grid-template-columns: 20px 1fr; gap: 12px; align-items: start; }
.item .ms { color: __VERDE__; vertical-align: 0; margin-top: 2px; }
.item.alta .ms { color: __VERMELHO__; } .item.media .ms { color: __AMBAR__; }
.item .tit { font-weight: 600; color: __TINTA__; }
.item .txt { color: __TINTA__; margin-top: 2px; line-height: 1.5; max-width: 72ch; }
.prio { margin-left: 10px; font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: __ROTULO__; }
.prio.alta { color: __VERMELHO__; } .prio.media { color: __AMBAR__; }
.stButton > button[kind="tertiary"] { border: 0; background: transparent; color: __VERDE__; min-height: 36px; padding: 0 6px; }
.stButton > button[kind="tertiary"]:hover { background: __VERDE_TINTA__; color: __VERDE_ESCURO__; }
/* Linha de ação do comprovante: altura fixa; o estado troca o conteúdo, nunca empurra o layout */
[class*="st-key-acao_dup_"] { min-height: 44px; gap: 12px; flex-wrap: wrap; }
.acao-msg { display: inline-flex; align-items: center; gap: 6px; font-weight: 500; color: __TINTA__; }
.acao-msg .ms { vertical-align: 0; color: __VERDE__; }
.acao-msg.alerta, .acao-msg.alerta .ms { color: __AMBAR__; } .acao-msg.ok, .acao-msg.ok .ms { color: __VERDE_ESCURO__; }

/* ── Passos (importação) ──────────────────────────────────────────────── */
.passos { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: __FIO__; border: 1px solid __FIO__;
          border-radius: 8px; overflow: hidden; margin: 4px 0 20px; }
.passo { background: #fff; padding: 10px 14px; color: __ROTULO__; display: flex; align-items: center; gap: 10px; }
.passo b { display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 999px; border: 1px solid __FIO__;
           font-size: 12px; color: __ROTULO__; }
.passo b .ms { font-size: 16px; vertical-align: 0; }
.passo.ativo { box-shadow: inset 0 0 0 2px __VERDE__; color: __TINTA__; font-weight: 600; }
.passo.ativo b, .passo.feito b { background: __VERDE__; border-color: __VERDE__; color: #fff; }
.passo.feito { color: __TINTA__; }

/* ── Chat ─────────────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] { background: transparent; padding: .5rem 0; gap: 16px; }
[data-testid="stChatMessage"]:has(.msg-usuario) > div:first-child { display: none; }
.msg-usuario { background: __VERDE_TINTA__; border: 1px solid __VERDE_FIO__; border-radius: 8px; padding: 8px 14px 10px; }
.msg-usuario p { margin: 2px 0 0; font-size: 15px; font-weight: 600; color: __TINTA__; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] :is(p, li) { font-size: 15px; line-height: 24px; }
[data-testid="stChatMessage"] [data-testid^="stChatMessageAvatar"] {
    width: 32px; height: 32px; border-radius: 999px; background: #fff; border: 1px solid __FIO__; color: __VERDE__;
}
[data-testid="stChatMessage"] table { display: block; max-width: 100%; overflow-x: auto; }
.passo-ferr { display: grid; grid-template-columns: 24px 1fr; gap: 10px; padding: 10px 0; border-bottom: 1px solid __FIO__; }
.passo-ferr:last-child { border-bottom: 0; }
.passo-ferr .campos { margin: 10px 0 4px; }
.passo-ferr .nota { color: __ROTULO__; font-size: 12px; line-height: 16px; margin-top: 4px; }
.passo-ferr .ms { color: __VERDE__; vertical-align: 0; }
.passo-ferr .t { font-weight: 600; color: __TINTA__; }
.passo-ferr .r { color: __TINTA__; margin-top: 2px; }
.fonte { border: 1px solid __FIO__; border-radius: 8px; padding: 10px 12px; margin: 8px 0; }
.fonte .f { font-weight: 600; color: __TINTA__; display: flex; gap: 6px; align-items: center; }
.fonte .f .ms { color: __VERDE__; font-size: 18px; vertical-align: 0; }
.fonte .x { color: __ROTULO__; margin-top: 4px; line-height: 1.5; }
details.tecnico { margin-top: 10px; font-size: 12px; color: __ROTULO__; }
details.tecnico summary { cursor: pointer; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }
details.tecnico div { font-family: ui-monospace, Consolas, monospace; margin-top: 4px; overflow-wrap: anywhere; }
.aviso { display: flex; gap: 8px; align-items: flex-start; border: 1px solid __AMBAR_FIO__; background: __AMBAR_FUNDO__;
         color: __AMBAR__; border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
.aviso.erro { border-color: __ERRO_FIO__; background: __VERMELHO_FUNDO__; color: __VERMELHO__; }
.aviso.ok { border-color: __OK_FIO__; background: __VERDE_TINTA__; color: __VERDE_ESCURO__; }
.aviso .ms { vertical-align: 0; font-size: 20px; }
[data-testid="stExpander"] > details { border: 1px solid __FIO__; border-radius: 8px; }
[data-testid="stExpander"] summary { font-weight: 500; }
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] { color: __VERDE__; }

/* Campo de pergunta */
[data-testid="stChatInput"] { border: 1px solid __FIO__ !important; border-radius: 8px; background: #fff !important; }
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] > div > div, [data-testid="stChatInput"] > div > div > div {
    background: #fff !important; border: 0 !important; box-shadow: none !important; }
[data-testid="stChatInputTextArea"] { background: #fff !important; color: __TINTA__; }
[data-testid="stChatInput"] { position: relative; }
[data-testid="stChatInput"]::before {
    content: "Pergunta"; position: absolute; top: 6px; left: 14px; z-index: 1; pointer-events: none;
    font-size: 12px; line-height: 16px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: __ROTULO__;
}
[data-testid="stChatInputTextArea"] { padding-top: 26px !important; }
[data-testid="stChatInput"]:focus-within { border-color: __VERDE__; box-shadow: inset 0 0 0 1px __VERDE__; }
[data-testid="stChatInputSubmitButton"] { background: __VERDE__; border-radius: 999px; }
[data-testid="stChatInputSubmitButton"] svg, [data-testid="stChatInputSubmitButton"] [data-testid="stIconMaterial"] { color: #fff; fill: #fff; }
[data-testid="stChatInputSubmitButton"]:disabled { background: __FIO__; }
[data-testid="stBottom"] > div { background: #fff; }

/* Conversa vazia */
.vazio { max-width: 720px; margin: 8px 0 0; }
.vazio h2 { font-size: 20px !important; line-height: 28px; font-weight: 600; margin: 0 0 4px; padding: 0; }
.vazio p { color: __ROTULO__; margin: 0 0 16px; max-width: 62ch; line-height: 1.55; }
.st-key-sugestoes { max-width: 720px; gap: 8px; }
.st-key-sugestoes button { min-height: 48px; justify-content: flex-start; text-align: left; padding: 10px 14px; }
.st-key-sugestoes button > div, .st-key-sugestoes button > div > span { justify-content: flex-start; width: 100%; }
.st-key-sugestoes button [data-testid="stMarkdownContainer"], .st-key-sugestoes button .stMarkdownEllipsis { overflow: visible; width: 100%; }
.st-key-sugestoes button p { white-space: normal; text-align: left; line-height: 1.4; }
.st-key-sugestoes button [data-testid="stIconMaterial"] { color: __VERDE__; }

/* ── Botões ───────────────────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button {
    border-radius: 8px; border: 1px solid __FIO__; background: #fff; color: __TINTA__; font-weight: 600; min-height: 40px;
    transition: border-color .15s ease-out, background .15s ease-out;
}
.stButton > button:hover, .stDownloadButton > button:hover { border-color: __VERDE__; color: __VERDE__; background: #fff; }
.stButton > button[kind="primary"] { background: __VERDE__; border-color: __VERDE__; color: #fff; }
.stButton > button[kind="primary"]:hover { background: __VERDE_ESCURO__; border-color: __VERDE_ESCURO__; color: #fff; }
.stButton > button:disabled { color: __ROTULO__; background: __SUPERFICIE__; }

/* Uploader */
[data-testid="stFileUploaderDropzone"] { background: #fff; border: 1px dashed __VERDE__; border-radius: 8px; padding: 20px 24px;
    display: flex; flex-direction: row; align-items: center; justify-content: flex-start; gap: 16px; flex-wrap: wrap; }
[data-testid="stFileUploaderDropzone"]:hover { background: __VERDE_TINTA__; }
/* Textos do Streamlit vêm em inglês e não são configuráveis: escondemos e escrevemos os nossos */
[data-testid="stFileUploaderDropzoneInstructions"] { display: none; }
[data-testid="stFileUploaderDropzone"] button p { font-size: 0; }
[data-testid="stFileUploaderDropzone"] button p::after { content: "Escolher arquivo"; font-size: 15px; font-weight: 600; }
[data-testid="stFileUploaderDropzone"]::after { content: "ou arraste para cá · PDF, CSV ou Excel · até 200 MB"; color: __ROTULO__; font-size: 15px; }
[data-testid="stFileUploaderFile"] { border: 1px solid __FIO__; border-radius: 8px; padding: 4px 8px; }
.importar-grade { display: grid; grid-template-columns: 1fr; gap: 0; }
[data-testid="stDataFrame"] { border: 1px solid __FIO__; border-radius: 8px; overflow: hidden; }

/* ── Celular ──────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"], .block-container { padding-top: 4rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }
    .pagina-titulo { font-size: 24px !important; line-height: 32px; }
    .campos { grid-template-columns: 1fr 1fr; }
    .campos .f:last-child:nth-child(odd) { grid-column: 1 / -1; }
    [data-testid="stChatMessage"] [data-testid^="stChatMessageAvatar"] { display: none; }
    .campos.kpi .v { font-size: 20px; line-height: 28px; }
    .passos { grid-template-columns: 1fr; }
    .msg-usuario { max-width: 100%; }
}
</style>
"""


def _css() -> str:
    css = _CSS
    for nome in ("VERDE_ESCURO", "VERDE_TINTA", "VERDE_FIO", "VERDE", "BRANCO", "SUPERFICIE", "TINTA", "ROTULO", "FIO",
                 "AMBAR_FIO", "AMBAR_FUNDO", "AMBAR", "VERMELHO_FUNDO", "VERMELHO", "OK_FIO", "ERRO_FIO", "GRADE"):
        css = css.replace(f"__{nome}__", globals()[nome])
    return css


def aplicar_tema():
    st.markdown(_css(), unsafe_allow_html=True)


def esc(texto) -> str:
    return html.escape(str(texto))


def ms(nome: str) -> str:
    """Ícone Material Symbols em HTML (decorativo: o texto ao lado carrega o significado)."""
    return f'<span class="ms" aria-hidden="true">{esc(nome)}</span>'


def brl(valor, casas=0) -> str:
    """Formata em reais no padrão brasileiro: R$ 1.234.567 (negativo: −R$ 1.234)."""
    if valor is None:
        return "—"
    s = f"{abs(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"−R$ {s}" if valor < 0 else f"R$ {s}"


def cabecalho(titulo: str, contexto: str = "", icone: str = "location_on"):
    st.markdown(f'<h1 class="pagina-titulo">{esc(titulo)}</h1>', unsafe_allow_html=True)
    if contexto:
        st.markdown(f'<div class="pagina-ctx">{ms(icone)}{esc(contexto)}</div>', unsafe_allow_html=True)


def secao(titulo: str, subtitulo: str = ""):
    st.markdown(f'<div class="secao">{esc(titulo)}</div>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<div class="secao-sub">{esc(subtitulo)}</div>', unsafe_allow_html=True)


def campos(itens: list[dict], kpi: bool = False) -> str:
    """HTML de uma faixa de campos da nota (a assinatura visual do produto).

    itens: [{"rotulo", "valor", "estado": foco|alerta|ruim|None, "texto": bool, "icone": str|None,
             "sub": str|None, "sub_tom": bom|ruim|None, "sub_icone": str|None}]
    """
    partes = []
    for c in itens:
        classe = ("f " + (c.get("estado") or "") + (" largo" if c.get("largo") else "")).strip()
        icone = ms(c["icone"]) if c.get("icone") else ""
        valor = f'<div class="v{" txt" if c.get("texto") else ""}">{icone}{esc(c["valor"])}</div>'
        sub = ""
        if c.get("sub"):
            sub_ic = ms(c["sub_icone"]) if c.get("sub_icone") else ""
            sub = f'<div class="s {c.get("sub_tom") or ""}">{sub_ic}{esc(c["sub"])}</div>'
        partes.append(f'<div class="{classe}"><div class="lab">{esc(c["rotulo"])}</div>{valor}{sub}</div>')
    return f'<div class="campos{" kpi" if kpi else ""}">{"".join(partes)}</div>'


def mostrar_campos(itens: list[dict], kpi: bool = False):
    st.markdown(campos(itens, kpi), unsafe_allow_html=True)


def aviso(texto: str, tipo: str = "", icone: str = "info"):
    """Aviso inline com ícone. tipo: '' (atenção) | 'erro' | 'ok'."""
    st.markdown(f'<div class="aviso {tipo}">{ms(icone)}<div>{esc(texto)}</div></div>', unsafe_allow_html=True)


def layout_grafico(fig, altura=340):
    """Aplica o visual padrão a um gráfico Plotly."""
    fig.update_layout(
        height=altura, margin=dict(l=8, r=8, t=30, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Public Sans, sans-serif", color=TINTA, size=13),
        colorway=SERIE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        hoverlabel=dict(bgcolor="#fff", font_size=13, font_family="Public Sans, sans-serif"),
        separators=",.",
    )
    fig.update_xaxes(showgrid=False, linecolor=FIO)
    fig.update_yaxes(gridcolor=GRADE, zeroline=False)
    return fig
