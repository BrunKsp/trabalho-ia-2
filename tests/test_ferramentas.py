"""
Testes das ferramentas do servidor MCP contra o banco de demonstração.

Além de checar formato, verificam que cada ANOMALIA PLANTADA pelo
scripts/gerar_dados.py é encontrada — são as respostas que a demo promete.
"""
import pytest

from camposync import servidor_mcp as s
from camposync.config import DB_PATH


def test_usa_banco_de_teste(db_teste):
    assert DB_PATH == db_teste, "os testes devem usar a cópia, nunca o banco versionado"


def test_listar_fazendas():
    fazendas = s.listar_fazendas()
    assert [f["id"] for f in fazendas] == [1, 2, 3, 4]
    assert {"id", "nome", "municipio", "area_ha", "culturas"} <= set(fazendas[0])


def test_gastos_por_safra_soma_bate_com_categorias():
    r = s.gastos_por_safra(1, "2025/26", "soja")
    assert r["fazenda"] == "Fazenda Boa Vista"
    assert r["total_gasto"] > 0
    assert r["total_gasto"] == pytest.approx(sum(c["total"] for c in r["por_categoria"]), abs=0.1)
    # ordenado do maior para o menor gasto
    totais = [c["total"] for c in r["por_categoria"]]
    assert totais == sorted(totais, reverse=True)


def test_comparar_safras_encontra_fertilizante_caro():
    """Anomalia plantada: Fazenda Boa Vista, soja 2025/26, fertilizante +28%."""
    r = s.comparar_safras(1, "2024/25", "2025/26", "soja")
    por_cat = {c["categoria"]: c["variacao_pct"] for c in r["por_categoria"]}
    maior = max(por_cat, key=por_cat.get)
    assert maior == "Fertilizantes"
    assert por_cat["Fertilizantes"] > 25
    # as demais categorias variam pouco (só inflação)
    assert all(v < 10 for c, v in por_cat.items() if c != "Fertilizantes")


def test_resultado_safra_margem_consistente():
    r = s.resultado_safra(1, "2024/25")
    assert r["margem_bruta"] == pytest.approx(r["receita_bruta"] - r["despesa_total"], abs=0.1)
    assert r["margem_pct"] == pytest.approx(r["margem_bruta"] / r["receita_bruta"] * 100, abs=0.1)
    assert r["producao_sacas"] > 0


@pytest.mark.parametrize("fazenda_id, safra, cultura, categoria", [
    (1, "2025/26", "soja", "Fertilizantes"),         # fertilizante +28%
    (3, "2024/25", "milho", "Defensivos"),           # reaplicação por praga +35%
    (4, "2023/24", "milho", "Diesel e operacoes"),   # trator quebrado +30%
])
def test_detectar_anomalias_plantadas(fazenda_id, safra, cultura, categoria):
    alertas = s.detectar_anomalias(fazenda_id)
    assert any(
        a["safra"] == safra and a["cultura"] == cultura and a["categoria"] == categoria and a["desvio_pct"] > 20
        for a in alertas
    ), alertas


def test_fazenda_sem_anomalia():
    assert s.detectar_anomalias(2) == []


def test_detectar_duplicados_acha_o_plantado():
    r = s.detectar_duplicados(1)
    assert r["total_exatos"] == 1
    dup = r["exatos"][0]
    assert dup["data"] == "2023-10-05"
    assert dup["categoria"] == "Seguro e juros"
    assert dup["ocorrencias"] == 2 and len(dup["ids"]) == 2
    assert r["valor_total_em_excesso"] == pytest.approx(15854.30)


def test_detectar_duplicados_todas_as_fazendas():
    r = s.detectar_duplicados()
    assert r["fazenda_id"] == "todas"
    assert r["total_exatos"] == 1  # só existe o plantado


def test_detectar_duplicados_suspeitos_janela(db_teste):
    """Mesmo fornecedor e valor em datas próximas = suspeito; fora da janela, não."""
    import sqlite3
    con = sqlite3.connect(db_teste)
    try:
        con.executemany(
            "INSERT INTO lancamentos (id, fazenda_id, safra, cultura, data, categoria, fornecedor, valor, mensagem_whatsapp)"
            " VALUES (?, 2, '2025/26', 'soja', ?, 'Sementes', 'Fornecedor Teste', 1234.56, 'teste')",
            [(90001, "2025-10-01"), (90002, "2025-10-04"), (90003, "2025-12-20")],
        )
        con.commit()
        r = s.detectar_duplicados(2, janela_dias=7)
        pares = [sorted(x["ids"]) for x in r["suspeitos"]]
        assert [90001, 90002] in pares
        assert all(90003 not in p for p in pares)
        assert s.detectar_duplicados(2, janela_dias=1)["total_suspeitos"] == 0
    finally:
        con.execute("DELETE FROM lancamentos WHERE id >= 90000")
        con.commit()
        con.close()


def test_cotacoes():
    c = s.cotacao_atual("Soja")  # aceita maiúscula
    assert c["preco_saca"] > 0 and c["data"]
    assert "erro" in s.cotacao_atual("cafe")
    hist = s.historico_cotacoes("soja", "2024/25")
    assert len(hist) > 40  # semanal, ~52 semanas
    assert all("2024-07-01" <= h["data"] <= "2025-06-30" for h in hist)


def test_buscar_lancamentos_filtros_e_limite():
    r = s.buscar_lancamentos(1, safra="2025/26", categoria="Fert", limite=5)
    assert 0 < len(r) <= 5
    assert all(l["categoria"] == "Fertilizantes" for l in r)


def test_recomendar_acoes_ordenadas_por_prioridade():
    recs = s.recomendar_acoes(1)
    assert recs
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    prioridades = [ordem[r["prioridade"]] for r in recs]
    assert prioridades == sorted(prioridades)
    assert any(r["tipo"] == "alerta_custo" and r.get("categoria") == "Fertilizantes" for r in recs)
