# Dados do projeto

## 1. Base financeira sintética (`camposync_demo.db`)

Gerada por `python gerar_dados.py` (semente fixa, sempre reproduz os mesmos dados).

| Tabela | Conteúdo |
|---|---|
| `fazendas` | 4 fazendas fictícias no RS (área, município, culturas) |
| `plantios` | área, produtividade (sc/ha) e produção por fazenda, safra e cultura |
| `lancamentos` | despesas com data, categoria, fornecedor, valor e a mensagem de WhatsApp que o produtor teria enviado |
| `receitas` | vendas da produção (sacas, preço por saca, comprador) |
| `cotacoes` | preço semanal por saca de soja, milho e trigo (sintético) |

Safras 2022/23 a 2025/26. A estrutura de custo por categoria segue o modelo das planilhas de custo de produção da Conab, e o fator climático simula as quebras de safra no RS.

**Anomalias plantadas de propósito** (para testar se o agente encontra):
- Fazenda Boa Vista, soja 2025/26: fertilizante 28% mais caro.
- Granja Três Irmãos, milho 2024/25: defensivos 35% acima (reaplicação).
- Estância do Pai, 2023/24: diesel e operações 30% acima (trator quebrado).
- Um lançamento duplicado.

**Antes de entregar:** substitua os valores aproximados de `CUSTO_HA`, `PRECO` e da tabela `cotacoes` pelos dados oficiais:
- Conab: gov.br/conab → Informações Agropecuárias → Custos de Produção → Planilhas de custo de produção (séries históricas).
- CEPEA/Esalq: cepea.org.br → Indicadores → baixar a série em Excel (cadastro gratuito).

## 2. Base de conhecimento do RAG (`documentos/`)

Baixe com `python baixar_documentos.py`. Acrescente manualmente:
- Manual do LCDPR (site da Receita Federal, buscar "Manual LCDPR").
- Cartilhas de gestão rural da Emater/RS e do Senar.
- Planilhas de custo da Conab exportadas em PDF, se quiser que o agente cite os números oficiais.

Todos são documentos públicos; cite as fontes no README.
