# Consultor da Safra — CampoSync

> Trabalho 2 — IA II | Modalidade 3: Agente com MCP + RAG

Agente de IA que responde perguntas financeiras do produtor rural em linguagem natural, cruzando os dados de lançamentos do CampoSync com uma base de conhecimento do agro (Embrapa, Conab, LCDPR).

> ⚠️ **Os dados financeiros das fazendas são sintéticos** (gerados por `scripts/gerar_dados.py`), com estrutura de custos baseada nas planilhas de custo de produção da Conab. Os documentos da base de conhecimento são PDFs públicos reais.

---

## Problema e valor

**Quem é o usuário.** O pequeno e médio produtor de grãos do RS (soja, milho, trigo): administra a fazenda sozinho ou com a família, sem controller nem contador dedicado à gestão do dia a dia.

**A dor.**
- Os gastos ficam espalhados em notas fiscais, boletos, mensagens de WhatsApp e no caderno. Quando os números estão num sistema, ele responde *quanto* foi gasto, mas não *por quê*.
- No fim da safra o produtor percebe que a margem caiu e não sabe onde: foi o fertilizante, o diesel, o preço de venda? Descobrir isso exige montar planilhas e comparar safras à mão.
- Erros simples passam despercebidos e custam caro: uma nota lançada duas vezes, uma reaplicação de defensivo que não foi planejada.
- A informação técnica que ajudaria a decidir (custos de referência da Embrapa e da Conab, regras do LCDPR) existe, mas está em PDFs longos que ninguém tem tempo de ler.

**A solução.** Um consultor financeiro que o produtor consulta em português comum, como faria com um agrônomo ou contador de confiança:
- *"Por que essa safra custou mais?"* → o agente compara as safras, encontra que o **fertilizante subiu 33%** enquanto o resto acompanhou a inflação, e explica.
- *"Tem algo estranho nos meus gastos?"* → detecta desvios em relação ao histórico da própria fazenda e **lançamentos duplicados** (no demo: um seguro de R$ 15.854,30 lançado duas vezes).
- *"Como a Embrapa calcula o custo de produção?"* → busca nos documentos oficiais e **cita a fonte e a página**.
- Além do chat: painel com gráficos da safra, recomendações proativas e importação de notas/planilhas.

**Por que IA (e não só um relatório).** As perguntas do produtor são abertas e mudam a cada safra. O LLM entende a pergunta, decide quais consultas fazer (ferramentas MCP), combina os resultados e explica em linguagem simples. As contas, porém, **não são feitas pelo modelo**: todo número vem de uma ferramenta que consulta o banco, e o conhecimento técnico vem de trechos recuperados dos documentos (RAG). Isso reduz alucinação e torna cada resposta auditável: a interface mostra quais ferramentas foram usadas e quais fontes foram consultadas.

**Valor gerado.**
- **Tempo:** perguntas que exigiriam cruzar planilhas de várias safras são respondidas em segundos.
- **Dinheiro:** anomalias e duplicidades são apontadas antes de o produtor fechar a safra ou pagar de novo.
- **Decisão melhor:** o produtor chega na negociação com fornecedor ou na decisão de venda sabendo onde está o problema.
- **Acesso:** traz para o pequeno produtor um tipo de análise que hoje só fazendas grandes, com equipe de gestão, conseguem ter.

**Aplicação prática.** O projeto foi pensado como módulo do CampoSync: o servidor MCP expõe as consultas sobre a base real de lançamentos, e a mesma arquitetura aceita novas fontes (cotações em tempo real, lançamentos enviados por WhatsApp). Os próximos passos estão em [docs/ROADMAP.md](docs/ROADMAP.md).

---

## Arquitetura

```
Produtor (pergunta)
      │
      ▼
  app.py  ──── Streamlit (interface web)
      │
      ▼
  camposync/agente.py ── LLM (OpenRouter) com tool use
      │
      ▼
  camposync/cliente_mcp.py ── fastmcp.Client (list_tools / call_tool)
      ║
      ║  protocolo MCP (JSON-RPC sobre stdio) — servidor roda em SUBPROCESSO
      ║
  camposync/servidor_mcp.py ── 11 ferramentas FastMCP
      │
      ├── data/camposync_demo.db (SQLite) ── lançamentos, receitas, cotações
      └── camposync/rag.py ── ChromaDB + embeddings ONNX → data/documentos/ (PDFs)
```

**Como o MCP é usado de verdade:** o agente não importa as funções do servidor.
Ao iniciar, o `cliente_mcp.py` sobe `python -m camposync.servidor_mcp` como
subprocesso, pede a lista de ferramentas (`list_tools`) — nome, descrição e
JSON Schema dos parâmetros vêm do próprio servidor — e converte para o formato
de *tools* do LLM. Cada chamada do modelo vira um `call_tool` no protocolo MCP.
Consequências práticas:

- **Uma única fonte da verdade:** para dar uma nova habilidade ao agente basta
  criar uma função com `@mcp.tool()` no servidor; nada muda no agente.
- **Reutilizável:** o mesmo servidor funciona em qualquer host MCP (Claude
  Desktop, Cursor, VS Code) — veja "Usar o servidor em outro cliente MCP".
- A interface (painel, recomendações) também consulta o servidor via MCP.
- O índice do RAG é construído em segundo plano quando o servidor sobe, então
  as demais ferramentas respondem imediatamente.

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
| `recomendar_acoes` | Recomendações proativas por fazenda |
| `detectar_duplicados` | Lançamentos em duplicidade (exatos e suspeitos em até 7 dias) e o valor pago a mais |
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

# 3. Configurar a chave da API OpenRouter (modelos gratuitos)
copy .env.example .env        # Windows  (Linux/Mac: cp .env.example .env)
# edite o .env e cole a sua chave em OPENROUTER_API_KEY
# opcional: OPENROUTER_MODEL=<modelo> para tentar um modelo específico primeiro
# (sem chave a interface abre normalmente; só o chat avisa que falta a chave)

# 4. (Opcional) Baixar PDFs para o RAG
python scripts/baixar_documentos.py

# 5. (Opcional) Regenerar banco de dados
python scripts/gerar_dados.py
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
python -m camposync.agente
```

**Servidor MCP standalone (stdio):**
```bash
python -m camposync.servidor_mcp
```

**Listar as ferramentas via protocolo MCP (diagnóstico):**
```bash
python -m camposync.cliente_mcp
```

### Usar o servidor em outro cliente MCP

O servidor é independente da interface. Exemplo para o Claude Desktop
(`claude_desktop_config.json`) — ajuste os caminhos para a sua máquina:

```json
{
  "mcpServers": {
    "consultor-safra": {
      "command": "C:\\caminho\\trabalho-ia-2\\.venv\\Scripts\\python.exe",
      "args": ["-m", "camposync.servidor_mcp"],
      "env": { "PYTHONPATH": "C:\\caminho\\trabalho-ia-2" }
    }
  }
}
```

---

## Testes e avaliação

### Testes automatizados (sem LLM, sem internet)

```bash
pytest                 # 44 testes, ~20 s
pytest -m "not lento"  # pula o teste que consulta o índice do RAG
```

Os testes rodam sobre uma **cópia temporária** do banco (variável `CAMPOSYNC_DB`), nunca sobre o banco versionado.

| Arquivo | O que garante |
|---|---|
| `tests/test_ferramentas.py` | Cada ferramenta MCP retorna dados consistentes (margem = receita − despesa, somas por categoria) e **encontra todas as anomalias plantadas** (fertilizante, defensivos, diesel, duplicado) |
| `tests/test_protocolo_mcp.py` | O servidor sobe via stdio, anuncia as 11 ferramentas com descrição e schema, e o resultado via protocolo é idêntico à chamada direta. Erros voltam como JSON para o LLM |
| `tests/test_agente.py` | Laço do agente com um **LLM falso roteirizado**: executa ferramentas via MCP, devolve o resultado ao modelo, coleta fontes do RAG, respeita o limite de rodadas, troca de modelo em 429/erro do provedor, para com chave inválida e grava o log |
| `tests/test_parser.py` | Importação de CSV/Excel com nomes de coluna variados, valores em formato brasileiro e gravação no banco |

### Avaliação do agente (com o LLM real)

```bash
python scripts/avaliar_agente.py
```

Faz 8 perguntas de gabarito (anomalias plantadas, cálculos e perguntas ao RAG) e mede se o agente **escolheu a ferramenta certa** e se a **resposta contém os fatos esperados**. O relatório com todas as respostas fica em [docs/resultados/avaliacao_agente.md](docs/resultados/avaliacao_agente.md).

**Última execução (22/11/2026, modelo `nvidia/nemotron-3-ultra-550b-a55b:free`):**

| Métrica | Resultado |
|---|---|
| Seleção correta de ferramenta | **100%** (8/8) |
| Fatos esperados presentes na resposta | **100%** |
| Tempo mediano por pergunta | 17,7 s |

Observações: na pergunta sobre a Embrapa o modelo fez 6 buscas no RAG antes de responder (10 trechos de 4 documentos citados), o que mostra o valor do limite de rodadas do agente. A avaliação tem uma execução por pergunta; com modelos gratuitos o resultado pode variar entre execuções e modelos.

Um exemplo de log real dessas conversas está em [docs/resultados/log_exemplo.jsonl](docs/resultados/log_exemplo.jsonl).

### Logs

Cada pergunta respondida é registrada em `data/logs/AAAA-MM-DD.jsonl` (pergunta, modelo, ferramentas chamadas com argumentos e tempo, fontes do RAG e resposta). A pasta fica fora do git.

---

## Perguntas de demo

Abra a Fazenda Boa Vista e pergunte:

1. *"Qual foi o gasto total na safra 2025/26 com soja?"*
2. *"Por que essa safra custou mais do que a 2024/25?"* → agente deve encontrar o fertilizante caro
3. *"Qual a margem bruta da safra 2023/24?"*
4. *"Tem algum gasto fora do normal nas minhas fazendas?"*
5. *"Tem algum lançamento duplicado?"* → encontra o seguro de R$ 15.854,30 lançado duas vezes em 05/10/2023
6. *"Qual a cotação da soja hoje? Compensa vender agora?"*
7. *"O que é o LCDPR e preciso declarar?"* → usa o RAG

---

## Calibração dos dados (antes da entrega)

Para ter dados mais precisos, substitua os valores aproximados em `scripts/gerar_dados.py`:

1. **Custos por hectare** (`CUSTO_HA`): baixe as planilhas de custo de produção da Conab em gov.br/conab → Informações Agropecuárias → Custos de Produção
2. **Preços por safra** (`PRECO`): baixe a série histórica do [CEPEA](https://www.cepea.esalq.usp.br/br/indicador/soja.aspx) (cadastro gratuito)
3. Depois rode `python scripts/gerar_dados.py` para regenerar o banco

---

## Estrutura do projeto

```
trabalho-ia-2/
├── app.py                   # Interface Streamlit (ponto de entrada)
├── camposync/               # Pacote principal
│   ├── agente.py            # Agente LLM com tool use
│   ├── servidor_mcp.py      # Servidor FastMCP (11 ferramentas, incl. RAG)
│   ├── cliente_mcp.py       # Cliente MCP: sobe o servidor via stdio e chama as ferramentas
│   ├── rag.py               # Indexação e busca nos PDFs
│   ├── parser_documentos.py # Importa lançamentos de PDF/CSV/Excel
│   └── config.py            # Caminhos centralizados
├── ui/                      # Interface: tema, dados e uma página por arquivo
│   └── paginas/             # painel, consultor, importar, recomendacoes
├── tests/                   # Testes automatizados (pytest)
├── scripts/
│   ├── avaliar_agente.py    # Avaliação do agente com o LLM real
│   ├── gerar_dados.py       # Gerador de dados sintéticos
│   ├── baixar_documentos.py # Downloader de PDFs públicos
│   └── rodar.ps1            # Sobe o app no Windows
├── data/
│   ├── camposync_demo.db    # Banco SQLite (637 lançamentos)
│   ├── csv/                 # Tabelas exportadas em CSV
│   ├── documentos/          # PDFs da base de conhecimento (RAG)
│   ├── chroma_db/           # Índice vetorial (gerado automaticamente)
│   └── logs/                # Log das conversas do agente (gerado automaticamente)
├── docs/
│   ├── ROADMAP.md           # Plano e próximos passos
│   ├── DADOS.md             # Documentação dos dados
│   ├── resultados/          # Avaliação do agente, prints e logs de exemplo
│   └── trabalho/            # Enunciado e recado do professor
└── requirements.txt
```

---

## Tecnologias

| Componente | Tecnologia |
|---|---|
| LLM | Modelos gratuitos via OpenRouter (Gemma, Nemotron) com fallback |
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
