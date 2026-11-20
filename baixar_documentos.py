"""
Baixa documentos publicos (Embrapa, Conab, MAPA) para a base de conhecimento do RAG.
Rode na sua maquina:  pip install requests  &&  python baixar_documentos.py
Os PDFs vao para a pasta ./documentos
"""
import os, requests

DOCS = {
    # Embrapa - gestao e custos
    "embrapa_avaliacao_economica_soja_PR_RS.pdf":
        "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1062878/1/CT126.pdf",
    "embrapa_produtividade_soja_RS.pdf":
        "https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1077687/1/GermaniConcencoArtigoSojaEmbrapaCULTIVAR.pdf",
    # Conab - acompanhamento de safra e logistica
    "conab_boletim_safra_10o_lev_2025-26.pdf":
        "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/safra-de-graos/boletim-da-safra-de-graos/10o-levantamento-safra-2025-26/e-book_boletim-de-safras-10o-levantamento_2026.pdf",
    "conab_boletim_logistico_dez_2025.pdf":
        "https://www.gov.br/conab/pt-br/atuacao/logistica/boletim-logistico/boletim-logistico-dezembro-2025.pdf/@@download/file",
    # MAPA - agropecuaria brasileira em numeros
    "mapa_agropecuaria_em_numeros_ago_2026.pdf":
        "https://www.gov.br/agricultura/pt-br/assuntos/politica-agricola/todas-publicacoes-de-politica-agricola/agropecuaria-brasileira-em-numeros/abn-2026-08.pdf",
    # Artigos academicos sobre custos no RS
    "artigo_precos_custos_soja_RS_2010-2024.pdf":
        "https://publicacoeseventos.unijui.edu.br/index.php/salaoconhecimento/article/view/27839/26330",
    "artigo_custos_variaveis_soja_noroeste_RS.pdf":
        "https://e-revista.unioeste.br/index.php/gepec/article/download/26485/17421",
    "artigo_gestao_custos_milho_soja_UFRGS.pdf":
        "https://dialnet.unirioja.es/descarga/articulo/7095226.pdf",
}

os.makedirs("documentos", exist_ok=True)
for nome, url in DOCS.items():
    destino = os.path.join("documentos", nome)
    if os.path.exists(destino):
        print("ja existe:", nome); continue
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        if b"%PDF" not in r.content[:1024]:
            print("ATENCAO (nao veio PDF, baixe pelo navegador):", nome, url); continue
        open(destino, "wb").write(r.content)
        print(f"ok: {nome} ({len(r.content)//1024} KB)")
    except Exception as e:
        print("FALHOU:", nome, "->", e, "| baixe manualmente:", url)
