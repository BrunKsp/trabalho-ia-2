# Roadmap — Consultor da Safra (CampoSync)

> Trabalho 2 — IA II (Modalidade 3: agente com MCP + RAG)
> **Entrega:** 23/11/2026 às 12h (repositório no GitHub) · **Apresentação:** 23/11, pitch de 5–7 min

Legenda: ✅ feito · 🔄 em andamento · ⬜ a fazer

---

## Onde estamos

| Área | Estado |
|---|---|
| Agente com tool use + fallback de modelos (OpenRouter) | ✅ |
| Servidor FastMCP com 9 ferramentas sobre SQLite | ✅ |
| RAG sobre 8 PDFs (Embrapa, Conab, artigos) | ✅ |
| Interface Streamlit com upload de PDF/CSV/Excel | ✅ |
| Recomendações proativas (`recomendar_acoes`) | ✅ |
| Repositório organizado (`camposync/`, `scripts/`, `data/`, `docs/`) | ✅ |
| README alinhado ao código | 🔄 |
| Exemplos de resultados (prints, logs) | ⬜ |
| Roteiro do pitch e demo | ⬜ |
| Commits de todos os integrantes | ⬜ |

---

## Fase 0 — Bloqueantes da entrega (até 23/11, 12h)

Itens exigidos pelo enunciado. Sem eles a nota fica comprometida.

- [ ] **Commits de todos os integrantes.** Cada pessoa do grupo faz ao menos um commit real com a própria identidade; o enunciado zera a nota de quem não tiver evidência de contribuição.
- [ ] **Validar a execução do zero** em uma máquina limpa: clonar, criar venv, `pip install -r requirements.txt`, definir `OPENROUTER_API_KEY`, `streamlit run app.py`. Corrigir o que quebrar.
- [ ] **Conferir o `requirements.txt`**: o código usa `openai` (cliente do OpenRouter); confirmar que nada sobrou do `anthropic`.
- [ ] **Exemplos de resultados** em `docs/resultados/`: prints das perguntas de demo (README → "Perguntas de demo"), do upload de documento e das recomendações, mais um log de uma conversa.
- [ ] **Seção "Problema e valor" no README**: quem é o usuário, qual a dor, o que muda com a solução (o professor avalia problema real e valor gerado, não só tecnologia).
- [ ] **Deixar claro que os dados são sintéticos**, com estrutura de custos baseada nas planilhas da Conab.

## Fase 1 — Pitch e demo (véspera e manhã da entrega)

Roteiro sugerido para 7 minutos:

| Tempo | Conteúdo |
|---|---|
| 0:00–1:00 | **Dor:** o produtor rural registra gastos em WhatsApp, caderno e notas, e não sabe por que a safra custou mais. |
| 1:00–2:30 | **Solução:** agente que cruza os lançamentos da fazenda (MCP) com conhecimento técnico do agro (RAG). Mostrar a arquitetura em um slide. |
| 2:30–5:30 | **Demo ao vivo:** (1) gasto da safra, (2) "por que custou mais?" encontra o fertilizante +28%, (3) anomalias, (4) pergunta sobre LCDPR via RAG, (5) upload de documento. |
| 5:30–6:30 | **Impacto e próximos passos:** integração real com o CampoSync, WhatsApp, dados reais. |
| 6:30–7:00 | Fechamento e perguntas. |

- [ ] Ensaiar a demo completa pelo menos uma vez.
- [ ] **Plano B:** os modelos gratuitos do OpenRouter têm limite de taxa e podem falhar. Gravar a demo em vídeo curto e deixar capturas prontas.
- [ ] Todos os integrantes participam da apresentação (exigência do enunciado).
- [ ] Preparar respostas para: "por que dados sintéticos?", "como evita alucinação?", "por que MCP e RAG?".

## Fase 2 — Qualidade técnica (após a entrega, se houver continuidade)

- [ ] Testes automatizados das ferramentas MCP (`camposync/servidor_mcp.py`) contra o banco de demonstração.
- [ ] Avaliação do agente: conjunto fixo de perguntas com respostas esperadas (inclui as anomalias plantadas).
- [ ] Remover o banco do versionamento ou separar o banco de demonstração do banco de trabalho (hoje o upload grava no mesmo arquivo versionado).
- [ ] Tratamento de erros e logs estruturados no agente.
- [ ] Rodar o servidor MCP como processo separado (hoje o agente importa as funções diretamente).

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
| Modelo gratuito indisponível ou lento na demo | Lista de modelos com fallback, vídeo gravado e prints. |
| Integrante sem commits | Fase 0, primeiro item. |
| Primeira execução lenta (indexação do RAG) | Rodar uma vez antes da apresentação para criar `data/chroma_db/`. |
| Pergunta sobre dados sintéticos | Explicar a origem (Conab) e mostrar o plano de calibração. |
