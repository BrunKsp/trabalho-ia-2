"""Consultas de dados para a interface (com cache). Lê o mesmo banco que o agente."""
import sqlite3
import pandas as pd
import streamlit as st

from camposync.config import DB_PATH
# Dados "de negócio" (resultado, anomalias, recomendações) vêm do servidor MCP,
# o mesmo que o agente usa; gráficos usam SQL direto só por desempenho.
from camposync.cliente_mcp import chamar

# O banco guarda categorias sem acento; aqui só embelezamos para exibir.
NOMES_CATEGORIA = {
    "Diesel e operacoes": "Diesel e operações",
    "Mao de obra": "Mão de obra",
    "Assistencia tecnica": "Assistência técnica",
}


def nome_categoria(cat: str) -> str:
    return NOMES_CATEGORIA.get(cat, cat)


def _df(sql: str, params=()) -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def limpar_cache():
    """Chame depois de importar lançamentos para os gráficos refletirem o novo dado."""
    st.cache_data.clear()


@st.cache_data(show_spinner=False)
def fazendas() -> list[dict]:
    return chamar("listar_fazendas")


@st.cache_data(show_spinner=False)
def safras(fazenda_id: int) -> list[str]:
    df = _df("SELECT DISTINCT safra FROM plantios WHERE fazenda_id=? ORDER BY safra", (fazenda_id,))
    return df["safra"].tolist()


@st.cache_data(show_spinner=False)
def culturas(fazenda_id: int) -> list[str]:
    df = _df("SELECT DISTINCT cultura FROM plantios WHERE fazenda_id=? ORDER BY cultura", (fazenda_id,))
    return df["cultura"].tolist()


@st.cache_data(show_spinner=False)
def resultado(fazenda_id: int, safra: str, cultura: str | None) -> dict:
    return chamar("resultado_safra", {"fazenda_id": fazenda_id, "safra": safra, "cultura": cultura})


@st.cache_data(show_spinner=False)
def custos_por_categoria(fazenda_id: int, safra: str, cultura: str | None) -> pd.DataFrame:
    sql = "SELECT categoria, SUM(valor) AS total FROM lancamentos WHERE fazenda_id=? AND safra=?"
    params: list = [fazenda_id, safra]
    if cultura:
        sql += " AND cultura=?"
        params.append(cultura)
    df = _df(sql + " GROUP BY categoria ORDER BY total DESC", params)
    df["categoria"] = df["categoria"].map(nome_categoria)
    return df


@st.cache_data(show_spinner=False)
def evolucao(fazenda_id: int, cultura: str | None) -> pd.DataFrame:
    """Receita, despesa e margem por safra."""
    filtro = " AND cultura=?" if cultura else ""
    p = [fazenda_id] + ([cultura] if cultura else [])
    desp = _df(f"SELECT safra, SUM(valor) AS despesa FROM lancamentos WHERE fazenda_id=?{filtro} GROUP BY safra", p)
    rec = _df(f"SELECT safra, SUM(valor) AS receita FROM receitas WHERE fazenda_id=?{filtro} GROUP BY safra", p)
    df = desp.merge(rec, on="safra", how="outer").fillna(0).sort_values("safra")
    df["margem"] = df["receita"] - df["despesa"]
    return df


@st.cache_data(show_spinner=False)
def cotacoes(produto: str) -> pd.DataFrame:
    df = _df("SELECT data, preco_saca FROM cotacoes WHERE produto=? ORDER BY data", (produto,))
    df["data"] = pd.to_datetime(df["data"])
    return df


@st.cache_data(show_spinner=False)
def anomalias(fazenda_id: int) -> list[dict]:
    return chamar("detectar_anomalias", {"fazenda_id": fazenda_id})


@st.cache_data(show_spinner=False)
def recomendacoes(fazenda_id: int) -> list[dict]:
    return chamar("recomendar_acoes", {"fazenda_id": fazenda_id})


@st.cache_data(show_spinner=False)
def total_lancamentos(fazenda_id: int) -> int:
    return int(_df("SELECT COUNT(*) AS n FROM lancamentos WHERE fazenda_id=?", (fazenda_id,))["n"][0])
