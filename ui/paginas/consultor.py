"""Consultor: chat com o agente, mostrando de onde vem cada número de cada resposta.

Fluxo de uma pergunta (máquina de estados simples em st.session_state):
  1. a pergunta entra no chat como "pendente" e a página reroda com o campo de
     pergunta bloqueado (evita que uma segunda pergunta cancele a primeira);
  2. o agente responde → a pergunta vira "respondida" e a resposta é anexada;
     ou falha → a pergunta fica no chat como "erro", com mensagem na língua do
     produtor e o botão "Tentar de novo" (o detalhe técnico vai só para o log).

Cada resposta termina no comprovante: uma faixa de campos (valor, data,
categoria, fornecedor, origem) montada a partir do resultado das ferramentas.
"""
import json
import logging
import os
import time

import streamlit as st

from camposync.agente import perguntar_detalhado  # carrega o .env como efeito colateral
from ui import dados, estado, tema

log = logging.getLogger("camposync.consultor")

AVATAR_USUARIO, AVATAR_AGENTE = ":material/person:", ":material/agriculture:"

# Nome da ferramenta MCP -> (ícone Material, o que ela fez, na língua do produtor)
FERRAMENTAS = {
    "listar_fazendas": ("home_work", "Consultou o cadastro de fazendas"),
    "gastos_por_safra": ("payments", "Somou os gastos da safra"),
    "comparar_safras": ("compare_arrows", "Comparou duas safras"),
    "resultado_safra": ("account_balance", "Calculou receita, despesa e margem"),
    "cotacao_atual": ("sell", "Buscou a cotação atual"),
    "historico_cotacoes": ("show_chart", "Consultou o histórico de preços"),
    "detectar_anomalias": ("warning", "Procurou gastos fora do padrão"),
    "buscar_lancamentos": ("receipt_long", "Consultou lançamentos da fazenda"),
    "recomendar_acoes": ("lightbulb", "Revisou o histórico para recomendar ações"),
    "detectar_duplicados": ("content_copy", "Procurou lançamentos duplicados"),
    "buscar_documentos": ("menu_book", "Pesquisou nos documentos da Embrapa e da Conab"),
}


# ── Formatação na língua do produtor ─────────────────────────────────────────
def _rotulo(nome: str):
    return FERRAMENTAS.get(nome, ("search", "Fez uma consulta"))


def _data_br(iso) -> str:
    s = str(iso or "")[:10]
    partes = s.split("-")
    return f"{partes[2]}/{partes[1]}/{partes[0]}" if len(partes) == 3 else s


def _pct(v) -> str:
    return f"{v:+.1f}%".replace(".", ",") if isinstance(v, (int, float)) else "—"


def _preco(v) -> str:
    return f"R$ {v:.2f}".replace(".", ",")


def _contexto_args(args: dict) -> str:
    """Safra e cultura consultadas, sem nomes de parâmetro."""
    partes = []
    for chave in ("safra", "safra_a", "safra_b"):
        if args.get(chave):
            partes.append(f"safra {args[chave]}")
    if args.get("cultura"):
        partes.append(str(args["cultura"]))
    if args.get("categoria"):
        partes.append(str(args["categoria"]).lower())
    if args.get("produto"):
        partes.append(str(args["produto"]))
    return " · ".join(partes)


def _json(bruto):
    try:
        return json.loads(bruto)
    except (TypeError, ValueError):
        return None


def _resumo_resultado(nome: str, bruto: str) -> str:
    """O número-chave que cada consulta trouxe, em R$ / sacas / datas. Vazio se não souber resumir."""
    r = _json(bruto)
    if r is None:
        return ""
    if isinstance(r, dict) and r.get("erro"):
        return "Não encontrou dados para essa consulta."
    try:
        if nome == "gastos_por_safra":
            maior = r["por_categoria"][0] if r.get("por_categoria") else None
            extra = f"; maior gasto: {dados.nome_categoria(maior['categoria']).lower()} ({tema.brl(maior['total'])})" if maior else ""
            return f"Total gasto: {tema.brl(r['total_gasto'])}{extra}."
        if nome == "comparar_safras":
            cats = [c for c in r["por_categoria"] if c.get("variacao_pct") is not None]
            maior = max(cats, key=lambda c: c["variacao_pct"]) if cats else None
            txt = f"Custo total {_pct(r['total'].get('variacao_pct'))}"
            if maior:
                txt += f"; quem mais subiu: {dados.nome_categoria(maior['categoria']).lower()} ({_pct(maior['variacao_pct'])})"
            return txt + "."
        if nome == "resultado_safra":
            return (f"Receita {tema.brl(r['receita_bruta'])} − despesa {tema.brl(r['despesa_total'])} "
                    f"= margem {tema.brl(r['margem_bruta'])} ({_pct(r.get('margem_pct'))}).")
        if nome == "cotacao_atual":
            return f"{str(r['produto']).capitalize()}: {_preco(r['preco_saca'])} por saca em {_data_br(r['data'])}."
        if nome == "historico_cotacoes" and r:
            precos = [x["preco_saca"] for x in r]
            return f"{len(r)} semanas, de {_preco(min(precos))} a {_preco(max(precos))} por saca."
        if nome == "detectar_anomalias":
            if not r:
                return "Nenhum gasto fora do padrão."
            a = r[0]
            return (f"{len(r)} alerta(s); o maior: {dados.nome_categoria(a['categoria']).lower()} na safra "
                    f"{a['safra']} ({a['cultura']}), {_pct(a['desvio_pct'])} sobre a média.")
        if nome == "detectar_duplicados":
            if not r.get("exatos"):
                return "Nenhum lançamento repetido."
            d = r["exatos"][0]
            return (f"{tema.brl(d['valor'], 2)} de {dados.nome_categoria(d['categoria']).lower()}, "
                    f"{d['fornecedor']}, em {_data_br(d['data'])}: lançado {d['ocorrencias']} vezes.")
        if nome == "buscar_lancamentos":
            return f"{len(r)} lançamento(s) encontrados."
        if nome == "recomendar_acoes":
            altas = sum(1 for x in r if x.get("prioridade") == "alta")
            return f"{len(r)} recomendação(ões), {altas} de prioridade alta."
        if nome == "buscar_documentos":
            docs = {x.get("fonte") for x in r if isinstance(x, dict) and x.get("fonte")}
            return f"{len(r)} trecho(s) de {len(docs)} documento(s)."
        if nome == "listar_fazendas":
            return f"{len(r)} fazenda(s) cadastradas."
    except (KeyError, IndexError, TypeError, ValueError):
        return ""
    return ""


# ── Comprovante: os campos da nota que sustentam a resposta ──────────────────
def _campos_da_ferramenta(nome: str, bruto: str) -> list[dict]:
    """Campos (rótulo, valor, estado) para o comprovante. Vazio quando a consulta não tem número a mostrar."""
    r = _json(bruto)
    if r is None or (isinstance(r, dict) and r.get("erro")):
        return []
    try:
        if nome == "detectar_duplicados" and r.get("exatos"):
            d = r["exatos"][0]
            return [
                {"rotulo": "Valor repetido", "valor": tema.brl(d["valor"], 2), "estado": "foco"},
                {"rotulo": "Data", "valor": _data_br(d["data"])},
                {"rotulo": "Categoria", "valor": dados.nome_categoria(d["categoria"]), "texto": True},
                {"rotulo": "Fornecedor", "valor": d["fornecedor"], "texto": True},
                {"rotulo": "Origem", "valor": f"{d['ocorrencias']} lançamentos", "texto": True, "icone": "receipt_long"},
            ]
        if nome == "comparar_safras":
            cats = [c for c in r["por_categoria"] if c.get("variacao_pct") is not None]
            if not cats:
                return []
            m = max(cats, key=lambda c: c["variacao_pct"])
            safras = [k for k in m if k not in ("categoria", "variacao_pct")]
            return [
                {"rotulo": "Categoria", "valor": dados.nome_categoria(m["categoria"]), "texto": True},
                {"rotulo": f"Safra {safras[0]}", "valor": tema.brl(m[safras[0]])},
                {"rotulo": f"Safra {safras[1]}", "valor": tema.brl(m[safras[1]]), "estado": "foco"},
                {"rotulo": "Variação", "valor": _pct(m["variacao_pct"]), "estado": "alerta" if m["variacao_pct"] > 20 else None},
                {"rotulo": "Origem", "valor": "Lançamentos · 2 safras", "texto": True, "icone": "receipt_long", "largo": True},
            ]
        if nome == "resultado_safra":
            neg = r["margem_bruta"] < 0
            return [
                {"rotulo": "Receita bruta", "valor": tema.brl(r["receita_bruta"])},
                {"rotulo": "Despesa total", "valor": tema.brl(r["despesa_total"])},
                {"rotulo": "Margem bruta", "valor": tema.brl(r["margem_bruta"]), "estado": "foco ruim" if neg else "foco",
                 "sub": _pct(r.get("margem_pct")) + " da receita", "sub_tom": "ruim" if neg else "bom"},
                {"rotulo": "Produtividade", "valor": f"{r['produtividade_sc_ha']:.1f} sc/ha".replace(".", ",") if r.get("produtividade_sc_ha") else "—"},
                {"rotulo": "Origem", "valor": f"Receitas e lançamentos · safra {r['safra']}", "texto": True, "icone": "receipt_long", "largo": True},
            ]
        if nome == "gastos_por_safra" and r.get("por_categoria"):
            m = r["por_categoria"][0]
            return [
                {"rotulo": "Total gasto", "valor": tema.brl(r["total_gasto"]), "estado": "foco"},
                {"rotulo": "Maior gasto", "valor": dados.nome_categoria(m["categoria"]), "texto": True},
                {"rotulo": "Valor", "valor": tema.brl(m["total"])},
                {"rotulo": "Origem", "valor": f"Lançamentos · safra {r['safra']}", "texto": True, "icone": "receipt_long", "largo": True},
            ]
        if nome == "cotacao_atual":
            return [
                {"rotulo": "Produto", "valor": str(r["produto"]).capitalize(), "texto": True},
                {"rotulo": "Preço da saca", "valor": _preco(r["preco_saca"]), "estado": "foco"},
                {"rotulo": "Data", "valor": _data_br(r["data"])},
                {"rotulo": "Origem", "valor": f"Cotações · {r.get('praca', '')}", "texto": True, "icone": "show_chart"},
            ]
        if nome == "detectar_anomalias" and r:
            a = r[0]
            return [
                {"rotulo": "Categoria", "valor": f"{dados.nome_categoria(a['categoria'])} · {a['cultura']}", "texto": True},
                {"rotulo": f"Safra {a['safra']}", "valor": tema.brl(a["total"]), "estado": "foco"},
                {"rotulo": "Média da fazenda", "valor": tema.brl(a["media_historica"])},
                {"rotulo": "Desvio", "valor": _pct(a["desvio_pct"]), "estado": "alerta"},
                {"rotulo": "Origem", "valor": "Histórico de lançamentos", "texto": True, "icone": "receipt_long", "largo": True},
            ]
    except (KeyError, IndexError, TypeError, ValueError):
        return []
    return []


def _comprovante(meta: dict) -> list[dict]:
    """O comprovante da resposta: os campos da consulta mais importante que trouxe números."""
    prioridade = ["detectar_duplicados", "comparar_safras", "resultado_safra", "detectar_anomalias",
                  "gastos_por_safra", "cotacao_atual"]
    por_nome = {f["nome"]: f for f in meta.get("ferramentas", [])}
    for nome in prioridade:
        if nome in por_nome:
            itens = _campos_da_ferramenta(nome, por_nome[nome].get("resultado", ""))
            if itens:
                return itens
    return []


def _trecho(texto: str, limite: int = 240) -> str:
    """Corta o trecho do documento no fim de uma palavra, não no meio dela."""
    t = " ".join(str(texto).split())
    if len(t) <= limite:
        return t
    return t[:limite].rsplit(" ", 1)[0] + "…"


def _mensagem_erro(e: Exception) -> str:
    """Erro técnico → o que o produtor precisa saber (o detalhe vai para o log)."""
    t = str(e)
    if "OPENROUTER_API_KEY" in t or "Chave do OpenRouter" in t:
        return "O consultor não está conectado ao serviço de inteligência artificial. Avise quem configura o sistema."
    if "Nenhum modelo respondeu" in t:
        return "O consultor está com muita procura agora e não conseguiu responder. Sua pergunta ficou guardada: tente de novo em um minuto."
    if any(p in t.lower() for p in ("connection", "conex", "timed out", "timeout")):
        return "Sem conexão com a internet agora. Sua pergunta ficou guardada: tente de novo quando o sinal voltar."
    return "Não consegui responder essa pergunta agora. Ela ficou guardada: tente de novo e, se continuar, pergunte de outro jeito."


# ── Sugestões tiradas da própria fazenda ─────────────────────────────────────
def _sugestoes(fazenda: dict) -> list[tuple[str, str]]:
    """(ícone Material, pergunta). A primeira vem do maior alerta da fazenda."""
    fid = fazenda["id"]
    safras = dados.safras(fid)
    sug = []
    alertas = dados.anomalias(fid)
    if alertas:
        a = alertas[0]
        sug.append(("warning", f"Por que o gasto com {dados.nome_categoria(a['categoria']).lower()} da safra "
                               f"{a['safra']} ({a['cultura']}) ficou {abs(a['desvio_pct']):.0f}% acima da média?"))
    elif len(safras) >= 2:
        sug.append(("compare_arrows", f"Por que a safra {safras[-1]} custou mais que a {safras[-2]}?"))
    sug.append(("content_copy", "Tem algum lançamento duplicado?"))
    if safras:
        sug.append(("account_balance", f"Qual foi a margem bruta da safra {safras[-1]}?"))
    sug.append(("sell", "Qual a cotação da soja hoje? Compensa vender agora?"))
    sug.append(("menu_book", "O que é o LCDPR (livro caixa do produtor) e preciso declarar?"))
    return sug


# ── Estado da conversa ───────────────────────────────────────────────────────
def _chaves(fid: int):
    return f"chat_{fid}", f"processando_{fid}"


def _enfileirar(fid: int, fazenda_nome: str, texto: str):
    chave, proc = _chaves(fid)
    chat = st.session_state.setdefault(chave, [])
    contexto = f"[Fazenda selecionada: {fazenda_nome} (id={fid})] {texto}"
    chat.append({"role": "user", "texto": texto, "agente": contexto, "estado": "pendente"})
    st.session_state[proc] = True


def _tentar_de_novo(fid: int, idx: int):
    chave, proc = _chaves(fid)
    st.session_state[chave][idx]["estado"] = "pendente"
    st.session_state[proc] = True


def _nova_conversa(fid: int):
    chave, _ = _chaves(fid)
    st.session_state[f"{chave}_anterior"] = st.session_state.get(chave, [])
    st.session_state[chave] = []


def _desfazer_nova_conversa(fid: int):
    chave, _ = _chaves(fid)
    st.session_state[chave] = st.session_state.pop(f"{chave}_anterior", [])


def _historico_para_agente(chat: list[dict]) -> list[dict]:
    """Só o que de fato foi conversado: perguntas sem resposta ficam de fora, exceto a pendente."""
    msgs = []
    for m in chat:
        if m["role"] == "user" and m.get("estado") not in ("respondida", "pendente"):
            continue
        msgs.append({"role": m["role"], "content": m["agente"]})
    return msgs


# ── Ação sobre lançamentos duplicados ────────────────────────────────────────
def _acao_dup(lanc_id: int, novo_estado: str | None):
    st.session_state[f"dup_{lanc_id}"] = novo_estado


def _apagar_copia(lanc_id: int):
    linha = dados.apagar_lancamento(lanc_id)
    st.session_state[f"dup_{lanc_id}"] = "apagado" if linha else "sumiu"
    st.session_state[f"dup_linha_{lanc_id}"] = linha


def _desfazer_apagar(lanc_id: int):
    linha = st.session_state.pop(f"dup_linha_{lanc_id}", None)
    if linha:
        dados.restaurar_lancamento(linha)
    st.session_state[f"dup_{lanc_id}"] = None


def _acoes_duplicados(meta: dict, bloqueado: bool):
    for f in meta.get("ferramentas", []):
        if f["nome"] != "detectar_duplicados":
            continue
        r = _json(f.get("resultado"))
        exatos = r.get("exatos", []) if isinstance(r, dict) else []
        for d in exatos:
            for copia in sorted(d["ids"])[1:]:  # mantém o primeiro lançamento, oferece apagar as cópias
                st_atual = st.session_state.get(f"dup_{copia}")
                valor = tema.brl(d["valor"], 2)
                with st.container(key=f"acao_dup_{copia}", horizontal=True, vertical_alignment="center"):
                    if st_atual == "apagado":
                        st.markdown(f'<span class="acao-msg ok">{tema.ms("check_circle")}Cópia apagada: '
                                    f'{valor} a menos na safra {tema.esc(d["safra"])}.</span>', unsafe_allow_html=True)
                        st.button("Desfazer", key=f"desf_{copia}", icon=":material/undo:",
                                  on_click=_desfazer_apagar, args=(copia,), disabled=bloqueado)
                    elif st_atual == "sumiu":
                        st.markdown(f'<span class="acao-msg">{tema.ms("info")}Essa cópia já não existe mais no histórico.</span>',
                                    unsafe_allow_html=True)
                    elif st_atual == "confirmar":
                        st.markdown(f'<span class="acao-msg alerta">{tema.ms("help")}Apagar a cópia de {valor}? '
                                    "O original fica.</span>", unsafe_allow_html=True)
                        st.button("Sim, apagar a cópia", key=f"sim_{copia}", type="primary", icon=":material/delete:",
                                  on_click=_apagar_copia, args=(copia,), disabled=bloqueado)
                        st.button("Cancelar", key=f"nao_{copia}", on_click=_acao_dup, args=(copia, None))
                    else:
                        st.button("Apagar a cópia repetida", key=f"apagar_{copia}", type="primary",
                                  icon=":material/delete:", on_click=_acao_dup, args=(copia, "confirmar"),
                                  disabled=bloqueado)


# ── "Como cheguei nessa resposta" ────────────────────────────────────────────
def _mostrar_meta(meta: dict):
    ferr, fontes = meta.get("ferramentas", []), meta.get("fontes", [])
    if not ferr:
        tema.aviso("Resposta geral: não consultei os dados da sua fazenda nem os documentos técnicos.", "", "info")
        return
    n = len(ferr)
    with st.expander(f"Como cheguei nessa resposta · {n} consulta{'s' if n > 1 else ''}", icon=":material/receipt_long:"):
        passos, tecnico = "", []
        for f in ferr:
            ic, desc = _rotulo(f["nome"])
            ctx = _contexto_args(f["args"])
            res = _resumo_resultado(f["nome"], f.get("resultado", ""))
            passos += (
                f'<div class="passo-ferr">{tema.ms(ic)}<div>'
                f'<div class="t">{tema.esc(desc)}{(" · " + tema.esc(ctx)) if ctx else ""}</div>'
                + (f'<div class="r">{tema.esc(res)}</div>' if res else "")
                + "</div></div>"
            )
            args = ", ".join(f"{k}={v}" for k, v in f["args"].items() if v not in (None, ""))
            tecnico.append(f"{f['nome']}({args}) · {f['segundos']}s")
        st.markdown(passos, unsafe_allow_html=True)

        if fontes:
            st.markdown('<div class="lab" style="margin-top:12px">Documentos consultados</div>', unsafe_allow_html=True)
            vistos = set()
            for fo in fontes:
                chave = (fo["fonte"], fo.get("pagina"))
                if chave in vistos:
                    continue
                vistos.add(chave)
                pag = f" · página {fo['pagina']}" if fo.get("pagina") not in ("", None) else ""
                st.markdown(
                    f'<div class="fonte"><div class="f">{tema.ms("description")}{tema.esc(fo["fonte"])}{tema.esc(pag)}</div>'
                    f'<div class="x">“{tema.esc(_trecho(fo["texto"]))}”</div></div>',
                    unsafe_allow_html=True,
                )

        if meta.get("modelo"):
            tecnico.append(f"modelo: {meta['modelo']}")
        st.markdown(
            '<details class="tecnico"><summary>Detalhes técnicos</summary>'
            + "".join(f"<div>{tema.esc(t)}</div>" for t in tecnico) + "</details>",
            unsafe_allow_html=True,
        )


# ── Página ───────────────────────────────────────────────────────────────────
def _responder(fazenda: dict, chat: list[dict], idx: int):
    """Roda o agente para a pergunta pendente chat[idx], mostrando o progresso."""
    _, proc = _chaves(fazenda["id"])
    with st.chat_message("assistant", avatar=AVATAR_AGENTE):
        status = st.status("Lendo sua pergunta… costuma levar de 10 a 30 segundos.", expanded=True)
        status.write(":material/edit_note: Entendendo o que você perguntou")
        n = {"consultas": 0}
        inicio = time.time()

        def ao_chamar(nome, args):
            ic, desc = _rotulo(nome)
            n["consultas"] += 1
            status.write(f":material/{ic}: {desc}")
            status.update(label=f"Consultando seus dados… {n['consultas']} consulta{'s' if n['consultas'] > 1 else ''} até agora")

        try:
            r = perguntar_detalhado(_historico_para_agente(chat[: idx + 1]), ao_chamar)
            status.update(label=f"Pronto em {time.time() - inicio:.0f} s", state="complete", expanded=False)
            chat[idx]["estado"] = "respondida"
            chat.insert(idx + 1, {
                "role": "assistant", "texto": r["resposta"], "agente": r["resposta"],
                "meta": {k: r[k] for k in ("ferramentas", "fontes", "modelo")},
            })
        except Exception as e:  # noqa: BLE001 - o produtor vê uma mensagem clara; o detalhe vai para o log
            log.exception("Falha ao responder pergunta do consultor")
            status.update(label="Não consegui responder", state="error", expanded=False)
            chat[idx]["estado"] = "erro"
            chat[idx]["erro_msg"] = _mensagem_erro(e)
        finally:
            st.session_state[proc] = False
    st.rerun()


def render(fazenda: dict):
    fid = fazenda["id"]
    chave, proc = _chaves(fid)
    chat = st.session_state.setdefault(chave, [])
    processando = bool(st.session_state.get(proc))

    topo, acao = st.columns([4, 1], vertical_alignment="bottom")
    with topo:
        safras = dados.safras(fid)
        tema.cabecalho("Consultor", f"{fazenda['nome']} · {fazenda['municipio']}"
                       + (f" · safra {safras[-1]}" if safras else ""))
    with acao:
        if chat:
            st.button("Nova conversa", key=f"nova_{fid}", icon=":material/add_comment:", on_click=_nova_conversa,
                      args=(fid,), disabled=processando, use_container_width=True)

    if not os.environ.get("OPENROUTER_API_KEY"):
        tema.aviso("O consultor ainda não está conectado ao serviço de inteligência artificial, por isso não "
                   "consegue responder. Avise quem configura o sistema.", "", "link_off")

    # Pergunta vinda de outra página (ex.: "Investigar" no Painel)
    pendente_externa = st.session_state.pop("pergunta_pendente", None)
    if pendente_externa and not processando:
        _enfileirar(fid, fazenda["nome"], pendente_externa)
        st.rerun()

    pergunta = st.chat_input(
        "Aguarde a resposta…" if processando else f"Pergunte sobre a {fazenda['nome']}…",
        disabled=processando,
    )
    if pergunta and not processando:
        _enfileirar(fid, fazenda["nome"], pergunta)
        st.rerun()

    # Conversa vazia: perguntas tiradas desta fazenda
    if not chat:
        if st.session_state.get(f"{chave}_anterior"):
            c1, c2 = st.columns([4, 1], vertical_alignment="center")
            c1.caption("Conversa anterior apagada.")
            c2.button("Desfazer", key="desfazer_nova", icon=":material/undo:", on_click=_desfazer_nova_conversa,
                      args=(fid,), use_container_width=True)
        st.markdown(
            '<div class="vazio"><h2>O que você quer saber sobre a safra?</h2>'
            '<p>Pergunte do seu jeito. Eu consulto os lançamentos da fazenda e os documentos da Embrapa e da Conab, '
            'e mostro de onde vem cada número.</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="lab" style="margin-bottom:8px">Perguntas sobre esta fazenda</div>', unsafe_allow_html=True)
        with st.container(key="sugestoes"):
            for ic, texto in _sugestoes(fazenda):
                st.button(texto, key=f"sug_{texto}", icon=f":material/{ic}:", use_container_width=True,
                          on_click=estado.perguntar_ao_consultor, args=(texto,))
        return

    # Histórico
    pendente_idx = None
    for i, m in enumerate(chat):
        if m["role"] == "user":
            with st.chat_message("user", avatar=AVATAR_USUARIO):
                # .msg-usuario marca a pergunta do produtor para o CSS (alinhada à direita, sem avatar)
                st.markdown(f'<div class="msg-usuario"><div class="lab">Pergunta</div>'
                            f'<p>{tema.esc(m["texto"])}</p></div>', unsafe_allow_html=True)
                if m.get("estado") == "erro":
                    tema.aviso(m.get("erro_msg", ""), "erro", "error")
                    if i == len(chat) - 1:
                        st.button("Tentar de novo", key=f"retry_{fid}_{i}", icon=":material/refresh:",
                                  on_click=_tentar_de_novo, args=(fid, i), disabled=processando)
            if m.get("estado") == "pendente":
                pendente_idx = i
        else:
            with st.chat_message("assistant", avatar=AVATAR_AGENTE):
                st.markdown(m["texto"])
                meta = m.get("meta") or {}
                itens = _comprovante(meta)
                if itens:
                    tema.mostrar_campos(itens)
                if meta:
                    _acoes_duplicados(meta, bloqueado=processando)
                    _mostrar_meta(meta)

    if processando and pendente_idx is not None:
        _responder(fazenda, chat, pendente_idx)
    elif processando:  # nada pendente (ex.: execução interrompida): destrava o campo
        st.session_state[proc] = False
        st.rerun()
