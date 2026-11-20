"""
Servidor FastMCP - Consultor da Safra
Ferramentas que o agente usa para consultar os dados financeiros do produtor.

Uso:  python servidor_mcp.py
"""
import sqlite3, os
from datetime import date
from typing import Optional
from fastmcp import FastMCP

DB_PATH = os.path.join(os.path.dirname(__file__), "camposync_demo.db")

mcp = FastMCP("consultor-safra")


def _con():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ── 1. Listar fazendas ──────────────────────────────────────────────────────
@mcp.tool()
def listar_fazendas() -> list[dict]:
    """Retorna todas as fazendas cadastradas com área e culturas."""
    with _con() as con:
        rows = con.execute("SELECT id, nome, municipio, area_ha, culturas FROM fazendas").fetchall()
    return [dict(r) for r in rows]


# ── 2. Gastos por safra ─────────────────────────────────────────────────────
@mcp.tool()
def gastos_por_safra(
    fazenda_id: int,
    safra: str,
    cultura: Optional[str] = None,
) -> dict:
    """
    Retorna o total gasto por categoria em uma safra de uma fazenda.
    safra: formato '2024/25'. cultura: 'soja', 'milho' ou 'trigo' (opcional).
    """
    sql = """
        SELECT categoria, SUM(valor) AS total
        FROM lancamentos
        WHERE fazenda_id = ? AND safra = ?
    """
    params: list = [fazenda_id, safra]
    if cultura:
        sql += " AND cultura = ?"
        params.append(cultura)
    sql += " GROUP BY categoria ORDER BY total DESC"

    with _con() as con:
        faz = con.execute("SELECT nome FROM fazendas WHERE id = ?", (fazenda_id,)).fetchone()
        rows = con.execute(sql, params).fetchall()
        total = con.execute(
            "SELECT SUM(valor) FROM lancamentos WHERE fazenda_id=? AND safra=?" + (" AND cultura=?" if cultura else ""),
            params,
        ).fetchone()[0] or 0

    return {
        "fazenda": faz["nome"] if faz else "desconhecida",
        "safra": safra,
        "cultura": cultura or "todas",
        "total_gasto": round(total, 2),
        "por_categoria": [{"categoria": r["categoria"], "total": round(r["total"], 2)} for r in rows],
    }


# ── 3. Comparar safras ──────────────────────────────────────────────────────
@mcp.tool()
def comparar_safras(
    fazenda_id: int,
    safra_a: str,
    safra_b: str,
    cultura: Optional[str] = None,
) -> dict:
    """
    Compara gastos entre duas safras, retornando variação por categoria.
    Útil para responder 'por que minha safra custou mais?'.
    """
    def _gastos(safra):
        sql = "SELECT categoria, SUM(valor) AS t FROM lancamentos WHERE fazenda_id=? AND safra=?"
        p = [fazenda_id, safra]
        if cultura:
            sql += " AND cultura=?"
            p.append(cultura)
        sql += " GROUP BY categoria"
        with _con() as con:
            return {r["categoria"]: r["t"] for r in con.execute(sql, p).fetchall()}

    ga, gb = _gastos(safra_a), _gastos(safra_b)
    cats = sorted(set(ga) | set(gb))
    comparacao = []
    for c in cats:
        va, vb = ga.get(c, 0), gb.get(c, 0)
        var = ((vb - va) / va * 100) if va else None
        comparacao.append({"categoria": c, safra_a: round(va, 2), safra_b: round(vb, 2),
                            "variacao_pct": round(var, 1) if var is not None else None})

    total_a = sum(ga.values())
    total_b = sum(gb.values())
    var_total = (total_b - total_a) / total_a * 100 if total_a else None

    return {
        "fazenda_id": fazenda_id,
        "cultura": cultura or "todas",
        "total": {safra_a: round(total_a, 2), safra_b: round(total_b, 2),
                  "variacao_pct": round(var_total, 1) if var_total is not None else None},
        "por_categoria": comparacao,
    }


# ── 4. Resultado da safra (receita - despesa) ───────────────────────────────
@mcp.tool()
def resultado_safra(fazenda_id: int, safra: str, cultura: Optional[str] = None) -> dict:
    """
    Calcula receita bruta, despesa total e margem de uma safra.
    """
    p_base = [fazenda_id, safra]
    filtro_cult = " AND cultura=?" if cultura else ""
    p = p_base + ([cultura] if cultura else [])

    with _con() as con:
        faz = con.execute("SELECT nome FROM fazendas WHERE id=?", (fazenda_id,)).fetchone()
        despesa = con.execute(
            "SELECT COALESCE(SUM(valor),0) FROM lancamentos WHERE fazenda_id=? AND safra=?" + filtro_cult, p
        ).fetchone()[0]
        receita = con.execute(
            "SELECT COALESCE(SUM(valor),0) FROM receitas WHERE fazenda_id=? AND safra=?" + filtro_cult, p
        ).fetchone()[0]
        prod = con.execute(
            "SELECT SUM(producao_sacas) sacas, AVG(produtividade_sc_ha) prod FROM plantios WHERE fazenda_id=? AND safra=?" + filtro_cult, p
        ).fetchone()

    margem = receita - despesa
    return {
        "fazenda": faz["nome"] if faz else "desconhecida",
        "safra": safra,
        "cultura": cultura or "todas",
        "receita_bruta": round(receita, 2),
        "despesa_total": round(despesa, 2),
        "margem_bruta": round(margem, 2),
        "margem_pct": round(margem / receita * 100, 1) if receita else None,
        "producao_sacas": prod["sacas"],
        "produtividade_sc_ha": round(prod["prod"], 1) if prod["prod"] else None,
    }


# ── 5. Cotação atual ─────────────────────────────────────────────────────────
@mcp.tool()
def cotacao_atual(produto: str) -> dict:
    """
    Retorna a cotação mais recente de um produto: 'soja', 'milho' ou 'trigo'.
    """
    with _con() as con:
        row = con.execute(
            "SELECT data, preco_saca, praca FROM cotacoes WHERE produto=? ORDER BY data DESC LIMIT 1",
            (produto.lower(),),
        ).fetchone()
    if not row:
        return {"erro": f"produto '{produto}' não encontrado"}
    return {"produto": produto, "data": row["data"], "preco_saca": row["preco_saca"], "praca": row["praca"]}


# ── 6. Histórico de cotações ─────────────────────────────────────────────────
@mcp.tool()
def historico_cotacoes(produto: str, safra: str) -> list[dict]:
    """
    Retorna as cotações semanais de um produto durante uma safra específica.
    safra: '2024/25'
    """
    ano = int(safra[:4])
    inicio = f"{ano}-07-01"
    fim = f"{ano + 1}-06-30"
    with _con() as con:
        rows = con.execute(
            "SELECT data, preco_saca FROM cotacoes WHERE produto=? AND data BETWEEN ? AND ? ORDER BY data",
            (produto.lower(), inicio, fim),
        ).fetchall()
    return [dict(r) for r in rows]


# ── 7. Detectar anomalias ────────────────────────────────────────────────────
@mcp.tool()
def detectar_anomalias(fazenda_id: int) -> list[dict]:
    """
    Compara o gasto de cada categoria/safra com a média histórica da fazenda.
    Retorna itens com desvio acima de 20%.
    """
    with _con() as con:
        rows = con.execute("""
            SELECT safra, cultura, categoria,
                   SUM(valor) AS total,
                   AVG(SUM(valor)) OVER (PARTITION BY cultura, categoria) AS media
            FROM lancamentos
            WHERE fazenda_id=?
            GROUP BY safra, cultura, categoria
        """, (fazenda_id,)).fetchall()

    alertas = []
    for r in rows:
        if r["media"] and r["media"] > 0:
            desvio = (r["total"] - r["media"]) / r["media"] * 100
            if abs(desvio) > 20:
                alertas.append({
                    "safra": r["safra"], "cultura": r["cultura"],
                    "categoria": r["categoria"],
                    "total": round(r["total"], 2),
                    "media_historica": round(r["media"], 2),
                    "desvio_pct": round(desvio, 1),
                })
    return sorted(alertas, key=lambda x: abs(x["desvio_pct"]), reverse=True)


# ── 8. Buscar lançamentos ────────────────────────────────────────────────────
@mcp.tool()
def buscar_lancamentos(
    fazenda_id: int,
    safra: Optional[str] = None,
    categoria: Optional[str] = None,
    limite: int = 20,
) -> list[dict]:
    """
    Busca lançamentos individuais com filtro por fazenda, safra e/ou categoria.
    """
    sql = "SELECT id, data, cultura, categoria, fornecedor, valor, mensagem_whatsapp FROM lancamentos WHERE fazenda_id=?"
    p: list = [fazenda_id]
    if safra:
        sql += " AND safra=?"; p.append(safra)
    if categoria:
        sql += " AND categoria LIKE ?"; p.append(f"%{categoria}%")
    sql += f" ORDER BY data DESC LIMIT {int(limite)}"
    with _con() as con:
        rows = con.execute(sql, p).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    mcp.run()
