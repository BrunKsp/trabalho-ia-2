# Roadmap — Consultor da Safra (CampoSync)

> Trabalho 2 — IA II (Modalidade 3: agente com MCP + RAG)
> **Entrega:** 23/11/2026 às 12h (repositório no GitHub) · **Apresentação:** 23/11, pitch de 5–7 min

Legenda: ✅ feito · 🔄 em andamento · ⬜ a fazer

---

## Onde estamos

| Área | Estado |
|---|---|
| Agente com tool use + fallback de modelos (OpenRouter), limite de rodadas e log | ✅ |
| Servidor FastMCP com 11 ferramentas (inclui RAG e `detectar_duplicados`) | ✅ |
| Agente fala com o servidor pelo protocolo MCP (subprocesso stdio, `list_tools`/`call_tool`) | ✅ |
| RAG sobre 8 PDFs (Embrapa, Conab, artigos) | ✅ |
| Interface Streamlit (painel com gráficos, chat com transparência, upload, recomendações) | ✅ |
| Recomendações proativas (`recomendar_acoes`) | ✅ |
| Repositório organizado (`camposync/`, `scripts/`, `data/`, `docs/`) | ✅ |
| README alinhado ao código, com "Problema e valor" | ✅ |
| Testes automatizados (49, pytest) | ✅ |
| Avaliação do agente com LLM real (`scripts/avaliar_agente.py`) | ✅ |
| Commits de todos os integrantes | ✅ |
| Prints da interface em `docs/resultados/` | ⬜ |
| Roteiro do pitch ensaiado | ⬜ |

---

## Fase 0 — Bloqueantes da entrega (até 23/11, 12h)

Itens exigidos pelo enunciado. Sem eles a nota fica comprometida.

- [x] **Commits de todos os integrantes.** Cada pessoa do grupo faz ao menos um commit real com a própria identidade; o enunciado zera a nota de quem não tiver evidência de contribuição.
- [x] **Validar a execução do zero** em uma máquina limpa: clonar, criar venv, `pip install -r requirements.txt`, definir `OPENROUTER_API_KEY`, `streamlit run app.py`. Corrigir o que quebrar. *(Validado em venv limpo; app agora abre mesmo sem chave.)*
- [x] **Conferir o `requirements.txt`**: o código usa `openai` (cliente do OpenRouter); confirmar que nada sobrou do `anthropic`.
- [ ] **Exemplos de resultados** em `docs/resultados/`: a avaliação do agente (com as respostas completas) e o log de exemplo já estão lá; **faltam os prints da interface** (painel, chat com o expander "como cheguei nessa resposta", upload e recomendações).
- [x] **Seção "Problema e valor" no README**: quem é o usuário, qual a dor, o que muda com a solução (o professor avalia problema real e valor gerado, não só tecnologia).
- [x] **Deixar claro que os dados são sintéticos**, com estrutura de custos baseada nas planilhas da Conab.

## Fase 1 — Pitch e demo (véspera e manhã da entrega)

Roteiro sugerido para 7 minutos:

| Tempo | Conteúdo |
|---|---|
| 0:00–1:00 | **Dor:** o produtor rural registra gastos em WhatsApp, caderno e notas, e não sabe por que a safra custou mais. |
| 1:00–2:30 | **Solução:** agente que cruza os lançamentos da fazenda (MCP) com conhecimento técnico do agro (RAG). Mostrar a arquitetura em um slide. |
| 2:30–5:30 | **Demo ao vivo:** (1) gasto da safra, (2) "por que custou mais?" encontra o fertilizante +28%, (3) anomalias, (4) "tem lançamento duplicado?" (R$ 15.854,30), (5) pergunta à base técnica via RAG com fonte e página, (6) abrir o expander "como cheguei nessa resposta" para mostrar MCP + RAG. |
| 5:30–6:30 | **Impacto e próximos passos:** integração real com o CampoSync, WhatsApp, dados reais. |
| 6:30–7:00 | Fechamento e perguntas. |

- [ ] Ensaiar a demo completa pelo menos uma vez.
- [ ] **Plano B:** os modelos gratuitos do OpenRouter têm limite de taxa e podem falhar. Gravar a demo em vídeo curto e deixar capturas prontas.
- [ ] Todos os integrantes participam da apresentação (exigência do enunciado).
- [ ] Preparar respostas para: "por que dados sintéticos?", "como evita alucinação?", "por que MCP e RAG?" (argumentos no README: seções "Problema e valor" e "Arquitetura").
- [ ] Na máquina da apresentação: `.env` com a chave, abrir o app uma vez antes (índice do RAG) e, se possível, definir `OPENROUTER_MODEL` com um modelo pago para não depender da fila dos gratuitos.

## Fase 2 — Qualidade técnica (após a entrega, se houver continuidade)

- [x] Testes automatizados das ferramentas MCP, do protocolo, do laço do agente (LLM falso) e do parser — `tests/`.
- [x] Avaliação do agente: 8 perguntas de gabarito com métricas de seleção de ferramenta e fatos na resposta — `scripts/avaliar_agente.py`.
- [ ] Ampliar a avaliação (mais perguntas, várias execuções por pergunta para medir variância entre modelos).
- [ ] Remover o banco do versionamento ou separar o banco de demonstração do banco de trabalho (hoje o upload grava no mesmo arquivo versionado).
- [x] Tratamento de erros e logs estruturados no agente (troca de modelo em 429/erro, limite de rodadas, log JSONL em `data/logs/`).
- [x] Rodar o servidor MCP como processo separado (subprocesso stdio via `fastmcp.Client`).
- [ ] CI no GitHub Actions rodando `pytest` a cada push.

## Fase 3 — Dados reais e produto

- [ ] Calibrar `CUSTO_HA` e `PRECO` com as planilhas oficiais da Conab e a série do CEPEA/Esalq.
- [ ] Incluir o Manual do LCDPR (Receita Federal) e cartilhas Emater/RS e Senar na base do RAG.
- [ ] Entrada de lançamentos por WhatsApp (o banco já guarda a mensagem original).
- [ ] Cotações em tempo real em vez de série sintética.
- [ ] Autenticação e múltiplos produtores.
- [ ] Modelo pago ou próprio para maior estabilidade.

---

## Riscos

| Risco | Mitigação |
|---|---|
| Modelo gratuito indisponível ou lento na demo | Troca imediata de modelo em 429, memória do último modelo que funcionou, `OPENROUTER_MODEL` para um modelo pago, vídeo gravado e prints. |
| Upload ao vivo altera o banco versionado | Não commitar `data/camposync_demo.db` depois da demo (ou separar o banco — Fase 2). |
| Primeira execução lenta (indexação do RAG) | Rodar uma vez antes da apresentação para criar `data/chroma_db/`. |
| Pergunta sobre dados sintéticos | Explicar a origem (Conab) e mostrar o plano de calibração. |
