"""Consultor: chat com o agente, mostrando de onde vem cada número de cada resposta.

Fluxo de uma pergunta (máquina de estados simples em st.session_state):
  1. a pergunta entra no chat como "pendente" e a página reroda com o campo de
     pergunta bloqueado (evita que uma segunda pergunta cancele a primeira);
  2. o agente responde → a pergunta vira "respondida" e a resposta é anexada;
     ou falha → a pergunta fica no chat como "erro", com mensagem na língua do
     produtor e o botão "Tentar de novo" (o detalhe técnico vai só para o log).
"""
import json
import logging
import os
import time

import streamlit as st

from camposync.agente import perguntar_detalhado  # carrega o .env como efeito colateral
from ui import dados, estado, tema

log = logging.getLogger("camposync.consultor")

AVATAR_USUARIO, AVATAR_AGENTE = "🧑‍🌾", "🌾"

# Nome da ferramenta MCP -> (ícone, o que ela fez, na língua do produtor)
FERRAMENTAS = {
    "listar_fazendas": ("🏡", "Consultou o cadastro de fazendas"),
    "gastos_por_safra": ("💸", "Somou os gastos da safra"),
    "comparar_safras": ("⚖️", "Comparou duas safras"),
    "resultado_safra": ("📈", "Calculou receita, despesa e margem"),
    "cotacao_atual": ("🌾", "Buscou a cotação atual"),
    "historico_cotacoes": ("📉", "Consultou o histórico de preços"),
    "detectar_anomalias": ("🚨", "Procurou gastos fora do padrão"),
    "buscar_lancamentos": ("🧾", "Consultou lançamentos da fazenda"),
    "recomendar_acoes": ("💡", "Revisou o histórico para recomendar ações"),
    "detectar_duplicados": ("👯", "Procurou lançamentos duplicados"),
    "buscar_documentos": ("📚", "Pesquisou nos documentos da Embrapa e da Conab"),
}


# ── Formatação na língua do produtor ─────────────────────────────────────────
def _rotulo(nome: str):
    return FERRAMENTAS.get(nome, ("🔧", "Fez uma consulta"))


def _data_br(iso) -> str:
    s = str(iso or "")[:10]
    partes = s.split("-")
    return f"{partes[2]}/{partes[1]}/{partes[0]}" if len(partes) == 3 else s


def _pct(v) -> str:
    return f"{v:+.1f}%".replace(".", ",") if isinstance(v, (int, float)) else "—"


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


def _resumo_resultado(nome: str, bruto: str) -> str:
    """O número-chave que cada consulta trouxe, em R$ / sacas / datas. Vazio se não souber resumir."""
    try:
        r = json.loads(bruto)
    except (TypeError, ValueError):
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
            total = r["total"].get("variacao_pct")
            txt = f"Custo total {_pct(total)}"
            if maior:
                txt += f"; quem mais subiu: {dados.nome_categoria(maior['categoria']).lower()} ({_pct(maior['variacao_pct'])})"
            return txt + "."
        if nome == "resultado_safra":
            return (f"Receita {tema.brl(r['receita_bruta'])} − despesa {tema.brl(r['despesa_total'])} "
                    f"= margem {tema.brl(r['margem_bruta'])} ({_pct(r.get('margem_pct'))}).")
        if nome == "cotacao_atual":
            preco = f"{r['preco_saca']:.2f}".replace(".", ",")
            return f"{str(r['produto']).capitalize()}: R$ {preco} por saca em {_data_br(r['data'])}."
        if nome == "historico_cotacoes" and r:
            precos = [x["preco_saca"] for x in r]
            return (f"{len(r)} semanas, de R$ {min(precos):.2f} a R$ {max(precos):.2f} por saca.").replace(".", ",", 2)
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
    fid = fazenda["id"]
    safras = dados.safras(fid)
    sug = []
    alertas = dados.anomalias(fid)
    if alertas:
        a = alertas[0]
        sug.append(("🚨", f"Por que {dados.nome_categoria(a['categoria']).lower()} da safra {a['safra']} "
                          f"({a['cultura']}) ficou {abs(a['desvio_pct']):.0f}% acima da média?"))
    elif len(safras) >= 2:
        sug.append(("🔎", f"Por que a safra {safras[-1]} custou mais que a {safras[-2]}?"))
    sug.append(("👯", "Tem algum lançamento duplicado?"))
    if safras:
        sug.append(("📈", f"Qual foi a margem bruta da safra {safras[-1]}?"))
    sug.append(("🌾", "Qual a cotação da soja hoje? Compensa vender agora?"))
    sug.append(("📚", "O que é o LCDPR (livro caixa do produtor) e preciso declarar?"))
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
        try:
            exatos = json.loads(f["resultado"]).get("exatos", [])
        except (TypeError, ValueError, AttributeError):
            continue
        for d in exatos:
            ids = sorted(d["ids"])
            for copia in ids[1:]:  # mantém o primeiro lançamento, oferece apagar as cópias
                desc = (f"{dados.nome_categoria(d['categoria'])} · {d['fornecedor']} · {_data_br(d['data'])} · "
                        f"<b>{tema.brl(d['valor'], 2)}</b>")
                st_atual = st.session_state.get(f"dup_{copia}")
                with st.container(key=f"acao_dup_{copia}"):
                    if st_atual == "apagado":
                        st.markdown(f'<div class="acao feito">✅ Cópia apagada. O custo da safra {tema.esc(d["safra"])} '
                                    f'ficou {tema.brl(d["valor"], 2)} menor; o lançamento original continua.</div>',
                                    unsafe_allow_html=True)
                        st.button("Desfazer", key=f"desf_{copia}", on_click=_desfazer_apagar, args=(copia,), disabled=bloqueado)
                    elif st_atual == "sumiu":
                        st.markdown('<div class="acao">Esse lançamento repetido já não existe mais no histórico.</div>',
                                    unsafe_allow_html=True)
                    elif st_atual == "confirmar":
                        st.markdown(f'<div class="acao"><b>Apagar a cópia repetida?</b><br>{desc}<br>'
                                    f'O lançamento original fica; só a cópia sai do histórico.</div>', unsafe_allow_html=True)
                        c1, c2 = st.columns(2)
                        c1.button("Sim, apagar a cópia", key=f"sim_{copia}", type="primary", use_container_width=True,
                                  on_click=_apagar_copia, args=(copia,), disabled=bloqueado)
                        c2.button("Cancelar", key=f"nao_{copia}", use_container_width=True,
                                  on_click=_acao_dup, args=(copia, None))
                    else:
                        st.markdown(f'<div class="acao">{desc}<br>Lançado {d["ocorrencias"]} vezes.</div>',
                                    unsafe_allow_html=True)
                        st.button("Apagar a cópia repetida", key=f"apagar_{copia}", on_click=_acao_dup,
                                  args=(copia, "confirmar"), disabled=bloqueado)


# ── "De onde vêm esses números" ──────────────────────────────────────────────
def _mostrar_meta(meta: dict):
    ferr, fontes = meta.get("ferramentas", []), meta.get("fontes", [])
    if not ferr:
        st.markdown('<div class="aviso-geral">⚠️ Resposta geral: não consultei os dados da sua fazenda '
                    'nem os documentos técnicos.</div>', unsafe_allow_html=True)
        return
    n = len(ferr)
    with st.expander(f"🔎 De onde vêm esses números · {n} consulta{'s' if n > 1 else ''}"):
        passos, tecnico = "", []
        for f in ferr:
            ic, desc = _rotulo(f["nome"])
            ctx = _contexto_args(f["args"])
            res = _resumo_resultado(f["nome"], f.get("resultado", ""))
            passos += (
                f'<div class="passo-ferr"><div class="ic">{ic}</div><div>'
                f'<div class="t">{tema.esc(desc)}{(" · " + tema.esc(ctx)) if ctx else ""}</div>'
                + (f'<div class="r">{tema.esc(res)}</div>' if res else "")
                + "</div></div>"
            )
            args = ", ".join(f"{k}={v}" for k, v in f["args"].items() if v not in (None, ""))
            tecnico.append(f"{f['nome']}({args}) · {f['segundos']}s")
        st.markdown(passos, unsafe_allow_html=True)

        if fontes:
            st.markdown('<div class="sub-rotulo">Documentos consultados</div>', unsafe_allow_html=True)
            vistos = set()
            for fo in fontes:
                chave = (fo["fonte"], fo.get("pagina"))
                if chave in vistos:
                    continue
                vistos.add(chave)
                pag = f" · página {fo['pagina']}" if fo.get("pagina") not in ("", None) else ""
                st.markdown(
                    f'<div class="fonte"><div class="f">📄 {tema.esc(fo["fonte"])}{tema.esc(pag)}</div>'
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
        status.write("📝 Entendendo o que você perguntou")
        n = {"consultas": 0}
        inicio = time.time()

        def ao_chamar(nome, args):
            ic, desc = _rotulo(nome)
            n["consultas"] += 1
            status.write(f"{ic} {desc}")
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

    tema.cabecalho("Consultor da Safra")
    culturas = fazenda["culturas"].replace(",", ", ")
    st.markdown(
        f'<div class="contexto-faz">📍 <b>{tema.esc(fazenda["nome"])}</b> · {tema.esc(fazenda["municipio"])} · '
        f'{fazenda["area_ha"]} ha · {tema.esc(culturas)}</div>',
        unsafe_allow_html=True,
    )

    if not os.environ.get("OPENROUTER_API_KEY"):
        st.warning("O consultor ainda não está conectado ao serviço de inteligência artificial, por isso não "
                   "consegue responder. Avise quem configura o sistema.")

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

    # Conversa vazia: sugestões tiradas desta fazenda
    if not chat:
        anterior = st.session_state.get(f"{chave}_anterior")
        if anterior:
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            c1.caption("Conversa anterior apagada.")
            c2.button("Desfazer", key="desfazer_nova", on_click=_desfazer_nova_conversa, args=(fid,),
                      use_container_width=True)
        st.markdown(
            '<div class="hero"><h2>Como posso ajudar na safra?</h2>'
            '<p>Pergunte do seu jeito. Eu consulto os lançamentos da fazenda e os documentos da Embrapa e da Conab, '
            'e mostro de onde vem cada número.</p></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="sugestoes"):
            for ic, texto in _sugestoes(fazenda):
                st.button(f"{ic}  {texto}", key=f"sug_{texto}", use_container_width=True,
                          on_click=estado.perguntar_ao_consultor, args=(texto,))
        return

    # Histórico
    pendente_idx = None
    for i, m in enumerate(chat):
        if m["role"] == "user":
            with st.chat_message("user", avatar=AVATAR_USUARIO):
                # .msg-usuario marca a bolha do produtor para o CSS (o avatar em emoji não tem test-id próprio)
                st.markdown(f'<p class="msg-usuario">{tema.esc(m["texto"])}</p>', unsafe_allow_html=True)
                if m.get("estado") == "erro":
                    st.markdown(f'<div class="erro-chat">{tema.esc(m.get("erro_msg", ""))}</div>',
                                unsafe_allow_html=True)
                    if i == len(chat) - 1:
                        st.button("↻ Tentar de novo", key=f"retry_{fid}_{i}", on_click=_tentar_de_novo,
                                  args=(fid, i), disabled=processando)
            if m.get("estado") == "pendente":
                pendente_idx = i
        else:
            with st.chat_message("assistant", avatar=AVATAR_AGENTE):
                st.markdown(m["texto"])
                if m.get("meta"):
                    _acoes_duplicados(m["meta"], bloqueado=processando)
                    _mostrar_meta(m["meta"])

    if processando and pendente_idx is not None:
        _responder(fazenda, chat, pendente_idx)
    elif processando:  # nada pendente (ex.: execução interrompida): destrava o campo
        st.session_state[proc] = False
        st.rerun()

    with st.container(key="rodape_chat"):
        st.button("🗑️ Nova conversa", key=f"nova_{fid}", on_click=_nova_conversa, args=(fid,))
