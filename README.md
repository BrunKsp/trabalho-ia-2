# Consultor da Safra — CampoSync

> Trabalho 2 — IA II | Modalidade 3: Agente com MCP + RAG

Agente de IA que responde perguntas financeiras do produtor rural em linguagem natural, cruzando os dados de lançamentos do CampoSync com uma base de conhecimento do agro (Embrapa, Conab, LCDPR).

---

## Arquitetura

```
Produtor (pergunta)
      │
      ▼
  app.py  ──── Streamlit (interface web)
      │
      ▼
  agente.py ── Claude claude-sonnet-4-6 com tool use
      │
      ├── servidor_mcp.py ── 8 ferramentas FastMCP → camposync_demo.db (SQLite)
      │
      └── rag.py ────────── ChromaDB + SentenceTransformers → documentos/ (PDFs)
```

**Ferramentas MCP disponíveis para o agente:**

| Ferramenta | O que faz |
|---|---|
| `listar_fazendas` | Lista fazendas cadastradas |
| `gastos_por_safra` | Total de gastos por categoria em uma safra |
| `comparar_safras` | Variação de custos entre duas safras |
| `resultado_safra` | Receita, despesa e margem de uma safra |
| `cotacao_atual` | Preço atual de soja/milho/trigo |
| `historico_cotacoes` | Série de preços durante uma safra |
| `detectar_anomalias` | Gastos acima de 20% da média histórica |
| `buscar_lancamentos` | Lançamentos individuais com filtros |
| `buscar_documentos` | RAG: busca em PDFs da Embrapa/Conab/LCDPR |

---

## Dados

Os dados financeiros são sintéticos, gerados por `gerar_dados.py` com estrutura de custos baseada nas [planilhas de custo de produção da Conab](https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/planilhas-de-custo-de-producao).

**Fazendas fictícias (RS):**
- Fazenda Boa Vista — Cachoeira do Sul — 180 ha — soja/trigo
- Sítio Santo Antônio — Santa Maria — 65 ha — soja
- Granja Três Irmãos — Cruz Alta — 420 ha — soja/milho/trigo
- Estância do Pai — Ijuí — 120 ha — milho/soja

**Anomalias plantadas para testar o agente:**
- Fazenda Boa Vista, soja 2025/26: fertilizante 28% mais caro
- Granja Três Irmãos, milho 2024/25: defensivos 35% acima (reaplicação por praga)
- Estância do Pai, 2023/24: diesel e operações 30% acima (trator quebrado)
- Um lançamento duplicado

**Base de conhecimento (RAG):**
- `embrapa_avaliacao_economica_soja_PR_RS.pdf` — avaliação econômica soja PR/RS
- `embrapa_produtividade_soja_RS.pdf` — produtividade de soja no RS
- `conab_boletim_safra_10o_lev_2025-26.pdf` — boletim de safra 2025/26
- `conab_boletim_logistico_dez_2025.pdf` — logística agrícola
- `artigo_precos_custos_soja_RS_2010-2024.pdf` — preços e custos soja RS
- `artigo_custos_variaveis_soja_noroeste_RS.pdf` — custos variáveis soja noroeste RS

**Adicionar manualmente:**
- Manual do LCDPR: buscar "Manual LCDPR" no site da Receita Federal
- Série histórica de preços: [CEPEA/Esalq](https://www.cepea.esalq.usp.br/br/indicador/) (cadastro gratuito)

---

## Instalação

```bash
# 1. Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar chave da API Anthropic
# Windows PowerShell:
$env:ANTHROPIC_API_KEY = "sk-ant-..."
# Linux/Mac:
# export ANTHROPIC_API_KEY="sk-ant-..."

# 4. (Opcional) Baixar PDFs para o RAG
python baixar_documentos.py

# 5. (Opcional) Regenerar banco de dados
python gerar_dados.py
```

---

## Como rodar

**Interface web (recomendado para demo):**
```bash
streamlit run app.py
```
Abre em `http://localhost:8501`

**Terminal (modo chat):**
```bash
python agente.py
```

**Servidor MCP standalone:**
```bash
python servidor_mcp.py
```

---

## Perguntas de demo

Abra a Fazenda Boa Vista e pergunte:

1. *"Qual foi o gasto total na safra 2025/26 com soja?"*
2. *"Por que essa safra custou mais do que a 2024/25?"* → agente deve encontrar o fertilizante caro
3. *"Qual a margem bruta da safra 2023/24?"*
4. *"Tem algum gasto fora do normal nas minhas fazendas?"*
5. *"Qual a cotação da soja hoje? Compensa vender agora?"*
6. *"O que é o LCDPR e preciso declarar?"* → usa o RAG

---

## Calibração dos dados (antes da entrega)

Para ter dados mais precisos, substitua os valores aproximados em `gerar_dados.py`:

1. **Custos por hectare** (`CUSTO_HA`): baixe as planilhas de custo de produção da Conab em gov.br/conab → Informações Agropecuárias → Custos de Produção
2. **Preços por safra** (`PRECO`): baixe a série histórica do [CEPEA](https://www.cepea.esalq.usp.br/br/indicador/soja.aspx) (cadastro gratuito)
3. Depois rode `python gerar_dados.py` para regenerar o banco

---

## Estrutura do projeto

```
trabalho-ia/
├── app.py               # Interface Streamlit
├── agente.py            # Agente Claude com tool use
├── servidor_mcp.py      # Ferramentas FastMCP (8 endpoints)
├── rag.py               # Indexação e busca nos PDFs
├── gerar_dados.py       # Gerador de dados sintéticos
├── baixar_documentos.py # Downloader de PDFs públicos
├── camposync_demo.db    # Banco SQLite (637 lançamentos)
├── requirements.txt
├── DADOS.md             # Documentação dos dados
├── documentos/          # PDFs para o RAG (criado pelo baixar_documentos.py)
├── chroma_db/           # Índice vetorial (criado automaticamente)
└── *.csv                # Tabelas exportadas em CSV
```

---

## Tecnologias

| Componente | Tecnologia |
|---|---|
| LLM | Claude Sonnet 4.6 (Anthropic) |
| Ferramentas | FastMCP |
| Banco de dados | SQLite |
| RAG — embeddings | ChromaDB DefaultEmbeddingFunction (ONNX MiniLM-L6-v2) |
| RAG — vetor store | ChromaDB |
| Interface | Streamlit |
| Dados | Sintéticos calibrados pela Conab |

---

## Fonte dos documentos públicos

- Embrapa Soja — [infoteca.cnptia.embrapa.br](https://www.infoteca.cnptia.embrapa.br)
- Conab — [gov.br/conab](https://www.gov.br/conab)
- MAPA — [gov.br/agricultura](https://www.gov.br/agricultura)
- Receita Federal — Manual do LCDPR
- Artigos acadêmicos de acesso aberto (UNIJUÍ, UNIOESTE, Dialnet)
