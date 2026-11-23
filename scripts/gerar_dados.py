"""
Gerador de dados sinteticos para o "Consultor da Safra" (Trabalho 2 - IA II).

Cria fazendas ficticias no RS com lancamentos financeiros realistas por safra,
seguindo a estrutura de custo por hectare das planilhas da Conab.

IMPORTANTE: os valores em CUSTO_HA sao APROXIMADOS. Antes da entrega, troque
pelos valores das planilhas de custo de producao da Conab (gov.br/conab ->
Custos de Producao -> Planilhas de custo de producao) e cite a fonte no README.

Uso:  python scripts/gerar_dados.py     (gera data/camposync_demo.db + data/csv/*.csv)
"""
import random, sqlite3, os
from datetime import date, timedelta
import pandas as pd

SEED = 42
random.seed(SEED)

# ---------------- CONFIGURACAO (edite aqui) ----------------
# Custo total aproximado por hectare (R$/ha) na safra base 2022/23
CUSTO_HA = {"soja": 4800, "milho": 6200, "trigo": 3600}

# Participacao de cada categoria no custo total (estrutura tipo Conab)
ESTRUTURA = {
    "soja":  {"Sementes": .11, "Fertilizantes": .24, "Defensivos": .22, "Diesel e operacoes": .11,
              "Mao de obra": .05, "Arrendamento": .12, "Assistencia tecnica": .02,
              "Seguro e juros": .05, "Frete e armazenagem": .08},
    "milho": {"Sementes": .16, "Fertilizantes": .30, "Defensivos": .14, "Diesel e operacoes": .11,
              "Mao de obra": .04, "Arrendamento": .10, "Assistencia tecnica": .02,
              "Seguro e juros": .05, "Frete e armazenagem": .08},
    "trigo": {"Sementes": .12, "Fertilizantes": .28, "Defensivos": .20, "Diesel e operacoes": .12,
              "Mao de obra": .05, "Arrendamento": .08, "Assistencia tecnica": .02,
              "Seguro e juros": .06, "Frete e armazenagem": .07},
}

# Variacao de preco dos insumos por safra (1.0 = safra base)
INDICE_CUSTO = {"2022/23": 1.00, "2023/24": 0.93, "2024/25": 0.97, "2025/26": 1.04}

# Produtividade media (sacas de 60 kg/ha) e fator climatico por safra no RS
PROD_BASE = {"soja": 52, "milho": 140, "trigo": 50}
CLIMA = {"2022/23": 0.55, "2023/24": 0.85, "2024/25": 0.72, "2025/26": 1.05}  # estiagem/enchente

# Preco medio recebido (R$/saca) por safra - aproximado, substitua pelo CEPEA
PRECO = {"soja":  {"2022/23": 165, "2023/24": 125, "2024/25": 128, "2025/26": 122},
         "milho": {"2022/23": 82,  "2023/24": 58,  "2024/25": 68,  "2025/26": 62},
         "trigo": {"2022/23": 88,  "2023/24": 70,  "2024/25": 72,  "2025/26": 68}}

FAZENDAS = [
    {"id": 1, "nome": "Fazenda Boa Vista",   "municipio": "Cachoeira do Sul", "area_ha": 180, "culturas": ["soja", "trigo"]},
    {"id": 2, "nome": "Sitio Santo Antonio", "municipio": "Santa Maria",      "area_ha": 65,  "culturas": ["soja"]},
    {"id": 3, "nome": "Granja Tres Irmaos",  "municipio": "Cruz Alta",        "area_ha": 420, "culturas": ["soja", "milho", "trigo"]},
    {"id": 4, "nome": "Estancia do Pai",     "municipio": "Ijui",             "area_ha": 120, "culturas": ["milho", "soja"]},
]

# Calendario (mes, ano relativo ao inicio da safra) em que cada categoria e paga
CALENDARIO = {
    "soja":  {"Sementes": [(10, 0)], "Fertilizantes": [(9, 0), (10, 0)], "Defensivos": [(11, 0), (12, 0), (1, 1), (2, 1)],
              "Diesel e operacoes": [(10, 0), (11, 0), (3, 1), (4, 1)], "Mao de obra": [(10, 0), (12, 0), (2, 1), (4, 1)],
              "Arrendamento": [(5, 1)], "Assistencia tecnica": [(11, 0), (2, 1)], "Seguro e juros": [(10, 0), (5, 1)],
              "Frete e armazenagem": [(4, 1), (5, 1)]},
    "milho": {"Sementes": [(8, 0)], "Fertilizantes": [(8, 0), (9, 0)], "Defensivos": [(10, 0), (11, 0), (12, 0)],
              "Diesel e operacoes": [(8, 0), (9, 0), (2, 1), (3, 1)], "Mao de obra": [(9, 0), (12, 0), (3, 1)],
              "Arrendamento": [(4, 1)], "Assistencia tecnica": [(10, 0), (1, 1)], "Seguro e juros": [(8, 0), (4, 1)],
              "Frete e armazenagem": [(3, 1), (4, 1)]},
    "trigo": {"Sementes": [(6, 1)], "Fertilizantes": [(5, 1), (6, 1)], "Defensivos": [(7, 1), (8, 1), (9, 1)],
              "Diesel e operacoes": [(6, 1), (10, 1), (11, 1)], "Mao de obra": [(6, 1), (11, 1)],
              "Arrendamento": [(11, 1)], "Assistencia tecnica": [(7, 1)], "Seguro e juros": [(6, 1), (11, 1)],
              "Frete e armazenagem": [(11, 1), (12, 1)]},
}
COLHEITA = {"soja": [(4, 1), (5, 1)], "milho": [(3, 1), (4, 1)], "trigo": [(11, 1), (12, 1)]}

FORNECEDORES = {
    "Sementes": ["Coop. Agricola Regional", "Sementes Sul", "Agropecuaria do Vale"],
    "Fertilizantes": ["Coop. Agricola Regional", "Fertisul Revenda", "Agro Insumos RS"],
    "Defensivos": ["Agro Insumos RS", "Coop. Agricola Regional", "Defesa Agricola Ltda"],
    "Diesel e operacoes": ["Posto Trevo", "Posto BR do Campo", "Oficina do Ze (manutencao)"],
    "Mao de obra": ["Diaristas safra", "Folha funcionario fixo"],
    "Arrendamento": ["Arrendamento - proprietario da terra"],
    "Assistencia tecnica": ["Eng. Agronomo consultor"],
    "Seguro e juros": ["Banco - custeio agricola", "Seguradora rural"],
    "Frete e armazenagem": ["Transportes Pampa", "Armazem da Cooperativa"],
}
COMPRADORES = ["Coop. Agricola Regional", "Trading Graos Sul", "Cerealista Pampeana"]

# Mensagens no estilo WhatsApp que o produtor mandaria (para demo e testes)
MSG = ["paguei {v} de {c} pra {f}", "lanca ai {v} {c} da {faz}", "{c} {v} reais, {f}",
       "registra gasto de {v} com {c}", "botei {v} em {c} hoje", "saiu {v} de {c} lá na {faz}"]
# ------------------------------------------------------------


def data_aleatoria(ano_ini, mes, rel):
    ano = ano_ini + rel
    return date(ano, mes, random.randint(1, 28))


def brl(v):
    return f"{v:,.0f}".replace(",", ".")


def gerar():
    lanc, receitas, plantios = [], [], []
    lid = rid = 1
    for faz in FAZENDAS:
        for safra, idx in INDICE_CUSTO.items():
            ano_ini = int(safra[:4])
            n = len(faz["culturas"])
            for cult in faz["culturas"]:
                # verao: soja e milho dividem a area; inverno: trigo usa a area da soja
                tem_milho = "milho" in faz["culturas"]
                frac = {"soja": 0.65 if tem_milho else 1.0, "milho": 0.35 if n > 1 else 1.0,
                        "trigo": 0.65 if tem_milho else 1.0}[cult]
                area = round(faz["area_ha"] * frac)
                custo_total_ha = CUSTO_HA[cult] * idx * random.uniform(0.92, 1.08)

                # Anomalias propositalmente plantadas para o agente detectar
                anomalia = {}
                if faz["id"] == 1 and safra == "2025/26" and cult == "soja":
                    anomalia["Fertilizantes"] = 1.28   # compra cara de adubo
                if faz["id"] == 3 and safra == "2024/25" and cult == "milho":
                    anomalia["Defensivos"] = 1.35      # reaplicacao por praga
                if faz["id"] == 4 and safra == "2023/24":
                    anomalia["Diesel e operacoes"] = 1.30  # trator quebrado

                for cat, share in ESTRUTURA[cult].items():
                    if cat == "Arrendamento" and faz["id"] in (2, 4):
                        continue  # terra propria
                    total_cat = custo_total_ha * share * area * anomalia.get(cat, 1.0)
                    parcelas = CALENDARIO[cult][cat]
                    pesos = [random.uniform(0.6, 1.4) for _ in parcelas]
                    for (mes, rel), p in zip(parcelas, pesos):
                        valor = round(total_cat * p / sum(pesos), 2)
                        d = data_aleatoria(ano_ini, mes, rel)
                        forn = random.choice(FORNECEDORES[cat])
                        msg = random.choice(MSG).format(v=brl(valor), c=cat.lower(), f=forn, faz=faz["nome"])
                        lanc.append({"id": lid, "fazenda_id": faz["id"], "safra": safra, "cultura": cult,
                                     "data": d.isoformat(), "categoria": cat, "fornecedor": forn,
                                     "valor": valor, "mensagem_whatsapp": msg})
                        lid += 1

                prod_sc_ha = PROD_BASE[cult] * CLIMA[safra] * random.uniform(0.88, 1.12)
                sacas = round(prod_sc_ha * area)
                plantios.append({"fazenda_id": faz["id"], "safra": safra, "cultura": cult, "area_ha": area,
                                 "produtividade_sc_ha": round(prod_sc_ha, 1), "producao_sacas": sacas})
                for mes, rel in COLHEITA[cult]:
                    s = sacas // len(COLHEITA[cult])
                    preco = round(PRECO[cult][safra] * random.uniform(0.95, 1.05), 2)
                    receitas.append({"id": rid, "fazenda_id": faz["id"], "safra": safra, "cultura": cult,
                                     "data": data_aleatoria(ano_ini, mes, rel).isoformat(),
                                     "comprador": random.choice(COMPRADORES), "sacas": s,
                                     "preco_saca": preco, "valor": round(s * preco, 2)})
                    rid += 1

    # Um lancamento duplicado (erro de digitacao comum) para o agente achar
    dup = dict(lanc[57]); dup["id"] = lid; lanc.append(dup)

    # Cotacoes semanais sinteticas (substitua pela serie real do CEPEA)
    cot = []
    d, fim = date(2022, 9, 5), date(2026, 11, 16)
    nivel = {"soja": 170.0, "milho": 85.0, "trigo": 95.0}
    alvo = {c: PRECO[c] for c in PRECO}
    while d <= fim:
        ano_ini = d.year if d.month >= 7 else d.year - 1
        safra = f"{ano_ini}/{str(ano_ini + 1)[2:]}"
        for c in nivel:
            ref = alvo[c].get(safra, list(alvo[c].values())[-1])
            nivel[c] += (ref - nivel[c]) * 0.08 + random.gauss(0, ref * 0.012)
            cot.append({"data": d.isoformat(), "produto": c, "praca": "RS (sintetico)",
                        "preco_saca": round(nivel[c], 2)})
        d += timedelta(days=7)

    return (pd.DataFrame(FAZENDAS).assign(culturas=lambda x: x.culturas.str.join(",")),
            pd.DataFrame(plantios), pd.DataFrame(lanc), pd.DataFrame(receitas), pd.DataFrame(cot))


if __name__ == "__main__":
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(raiz, "data")
    csv_dir = os.path.join(out, "csv")
    os.makedirs(csv_dir, exist_ok=True)
    fazendas, plantios, lanc, receitas, cot = gerar()
    db = os.path.join(out, "camposync_demo.db")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    for nome, df in [("fazendas", fazendas), ("plantios", plantios), ("lancamentos", lanc),
                     ("receitas", receitas), ("cotacoes", cot)]:
        df.to_sql(nome, con, index=False)
        df.to_csv(os.path.join(csv_dir, f"{nome}.csv"), index=False)
    con.close()
    print(f"OK: {len(lanc)} lancamentos, {len(receitas)} receitas, {len(cot)} cotacoes -> {db}")
