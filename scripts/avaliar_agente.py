"""
Avaliação do agente com o LLM de verdade (usa a OPENROUTER_API_KEY do .env).

Para cada pergunta do gabarito mede:
  - ferramentas: o agente chamou as ferramentas certas? (seleção de ferramenta)
  - fatos:       a resposta final contém os fatos esperados? (ex.: "fertiliz", "15.854")
  - tempo e modelo usado.

Os casos cobrem as anomalias plantadas em scripts/gerar_dados.py, perguntas
de cálculo e perguntas de conhecimento (RAG).

Uso:
    python scripts/avaliar_agente.py            # todos os casos
    python scripts/avaliar_agente.py 1 4        # só os casos 1 e 4

Gera docs/resultados/avaliacao_agente.md (relatório) e .json (respostas completas).
"""
import json, re, sys, time, unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from camposync.agente import perguntar_detalhado  # noqa: E402

SAIDA = RAIZ / "docs" / "resultados"

# ferramentas: conjuntos alternativos aceitos — basta UM deles estar contido nas chamadas
# fatos: cada item é uma lista de alternativas; basta UMA aparecer na resposta
CASOS = [
    {
        "fazenda": (1, "Fazenda Boa Vista"),
        "pergunta": "Qual foi o gasto total na safra 2025/26 com soja?",
        "ferramentas": [{"gastos_por_safra"}, {"resultado_safra"}],
        "fatos": [["2025/26"], ["r$"]],
    },
    {
        "fazenda": (1, "Fazenda Boa Vista"),
        "pergunta": "Por que a safra de soja 2025/26 custou mais do que a 2024/25?",
        "ferramentas": [{"comparar_safras"}],
        "fatos": [["fertiliz"], ["33", "28", "26"]],
    },
    {
        "fazenda": (1, "Fazenda Boa Vista"),
        "pergunta": "Qual a margem bruta da safra 2024/25?",
        "ferramentas": [{"resultado_safra"}],
        "fatos": [["margem"], ["negativ", "prejuizo", "-150", "150.7", "150,7", "-11"]],
    },
    {
        "fazenda": (3, "Granja Tres Irmaos"),
        "pergunta": "Tem algum gasto fora do normal na minha fazenda?",
        "ferramentas": [{"detectar_anomalias"}],
        "fatos": [["defensiv"], ["milho"], ["2024/25"]],
    },
    {
        "fazenda": (1, "Fazenda Boa Vista"),
        "pergunta": "Tem algum lançamento duplicado?",
        "ferramentas": [{"detectar_duplicados"}],
        "fatos": [["15.854", "15854"], ["seguro"]],
    },
    {
        "fazenda": (1, "Fazenda Boa Vista"),
        "pergunta": "Qual a cotação da soja hoje?",
        "ferramentas": [{"cotacao_atual"}],
        "fatos": [["129"]],
    },
    {
        "fazenda": (1, "Fazenda Boa Vista"),
        "pergunta": "Segundo a Embrapa, como é composto o custo de produção da soja?",
        "ferramentas": [{"buscar_documentos"}],
        "fatos": [["custo"], ["variave", "fixo", "operacional"]],
    },
    {
        "fazenda": (4, "Estancia do Pai"),
        "pergunta": "O que você recomenda para melhorar meus resultados?",
        "ferramentas": [{"recomendar_acoes"}, {"detectar_anomalias"}],
        "fatos": [["diesel", "custo", "margem"]],
    },
]


def _norm(txt: str) -> str:
    """minúsculas, sem acento — para comparar fatos de forma tolerante."""
    txt = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return txt.lower()


def avaliar(caso: dict) -> dict:
    fid, fnome = caso["fazenda"]
    msg = f"[Fazenda selecionada: {fnome} (id={fid})] {caso['pergunta']}"
    inicio = time.time()
    try:
        r = perguntar_detalhado([{"role": "user", "content": msg}])
        erro = None
    except Exception as e:  # noqa: BLE001
        r, erro = {"resposta": "", "ferramentas": [], "fontes": [], "modelo": None}, str(e)
    chamadas = [f["nome"] for f in r["ferramentas"]]
    resp = _norm(r["resposta"])
    ok_ferr = any(alt <= set(chamadas) for alt in caso["ferramentas"])
    fatos = [any(_norm(a) in resp for a in alts) for alts in caso["fatos"]]
    return {
        "pergunta": caso["pergunta"], "fazenda": fnome,
        "esperado": [sorted(a) for a in caso["ferramentas"]], "chamadas": chamadas,
        "ferramenta_ok": ok_ferr, "fatos_ok": sum(fatos), "fatos_total": len(fatos),
        "segundos": round(time.time() - inicio, 1), "modelo": r["modelo"], "erro": erro,
        "fontes": sorted({f"{f['fonte']} p.{f['pagina']}" for f in r["fontes"]}),
        "resposta": r["resposta"],
    }


def relatorio(res: list[dict]) -> str:
    validos = [r for r in res if not r["erro"]]
    n = len(validos) or 1
    acc_ferr = sum(r["ferramenta_ok"] for r in validos) / n
    acc_fatos = sum(r["fatos_ok"] for r in validos) / max(1, sum(r["fatos_total"] for r in validos))
    tempos = sorted(r["segundos"] for r in validos) or [0]
    linhas = [
        "# Avaliação do agente",
        "",
        f"Executada em {datetime.now():%d/%m/%Y %H:%M} com `scripts/avaliar_agente.py` "
        f"({len(res)} perguntas, LLM real via OpenRouter).",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| Seleção correta de ferramenta | **{acc_ferr:.0%}** ({sum(r['ferramenta_ok'] for r in validos)}/{len(validos)}) |",
        f"| Fatos esperados presentes na resposta | **{acc_fatos:.0%}** |",
        f"| Tempo mediano por pergunta | {tempos[len(tempos) // 2]:.1f} s |",
        f"| Perguntas com erro (modelo indisponível) | {len(res) - len(validos)} |",
        f"| Modelos que responderam | {', '.join(sorted({r['modelo'] for r in validos if r['modelo']})) or '-'} |",
        "",
        "| # | Pergunta | Esperado | Chamou | Ferramenta | Fatos | Tempo |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(res, 1):
        esp = " ou ".join("+".join(a) for a in r["esperado"])
        cham = ", ".join(r["chamadas"]) or ("erro" if r["erro"] else "—")
        linhas.append(
            f"| {i} | {r['pergunta']} | `{esp}` | `{cham}` | {'✅' if r['ferramenta_ok'] else '❌'} "
            f"| {r['fatos_ok']}/{r['fatos_total']} | {r['segundos']} s |"
        )
    linhas += ["", "## Respostas", ""]
    for i, r in enumerate(res, 1):
        linhas += [f"### {i}. {r['pergunta']} ({r['fazenda']})", ""]
        if r["erro"]:
            linhas += [f"> Erro: {r['erro']}", ""]
            continue
        linhas += [f"*Ferramentas:* `{', '.join(r['chamadas']) or 'nenhuma'}` · *modelo:* `{r['modelo']}`"]
        if r["fontes"]:
            linhas += [f"*Fontes (RAG):* {'; '.join(r['fontes'])}"]
        linhas += ["", re.sub(r"^", "> ", r["resposta"].strip(), flags=re.M), ""]
    return "\n".join(linhas)


def main():
    idx = [int(a) for a in sys.argv[1:]] or list(range(1, len(CASOS) + 1))
    res = []
    for i in idx:
        caso = CASOS[i - 1]
        print(f"[{i}/{len(CASOS)}] {caso['pergunta']}", flush=True)
        r = avaliar(caso)
        status = "ERRO " + r["erro"] if r["erro"] else (
            f"ferramenta {'ok' if r['ferramenta_ok'] else 'ERRADA'} {r['chamadas']} | "
            f"fatos {r['fatos_ok']}/{r['fatos_total']} | {r['segundos']}s | {r['modelo']}")
        print("   ->", status, flush=True)
        res.append(r)
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "avaliacao_agente.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (SAIDA / "avaliacao_agente.md").write_text(relatorio(res), encoding="utf-8")
    print(f"\nRelatório: {SAIDA / 'avaliacao_agente.md'}")


if __name__ == "__main__":
    main()
