"""
Módulo RAG: indexa PDFs da pasta data/documentos/ e retorna trechos relevantes.

Na primeira execução cria o índice em data/chroma_db/.
Dependências: pip install chromadb pypdf sentence-transformers
"""
import os, sys, hashlib, threading
from pathlib import Path

from .config import DOCS_DIR, CHROMA_DIR

_collection = None
_lock = threading.Lock()  # a indexação pode ser disparada pelo aquecimento e por uma busca ao mesmo tempo


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    with _lock:
        if _collection is not None:
            return _collection

        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        ef = DefaultEmbeddingFunction()
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col = client.get_or_create_collection("safra_docs", embedding_function=ef)

        # Indexa PDFs ainda não indexados
        if DOCS_DIR.exists():
            _indexar_novos(col)

        _collection = col  # só publica depois de indexado
        return _collection


def aquecer():
    """Cria/atualiza o índice antecipadamente (o servidor MCP chama isto em segundo plano ao subir)."""
    try:
        n = _get_collection().count()
        print(f"[RAG] índice pronto: {n} trechos", file=sys.stderr)
    except Exception as e:
        print(f"[RAG] falha ao aquecer o índice: {e}", file=sys.stderr)


def _indexar_novos(col, lote: int = 256):
    from pypdf import PdfReader

    ids_existentes = set(col.get(include=[])["ids"])
    for pdf in sorted(DOCS_DIR.glob("*.pdf")):
        try:
            ids, docs, metas = [], [], []
            reader = PdfReader(str(pdf))
            for i, page in enumerate(reader.pages):
                texto = page.extract_text() or ""
                if len(texto.strip()) < 50:
                    continue
                # Divide em chunks de ~500 chars com overlap de 100
                for j, chunk in enumerate(_chunkar(texto, 500, 100)):
                    doc_id = hashlib.md5(f"{pdf.name}_{i}_{j}".encode()).hexdigest()
                    if doc_id not in ids_existentes:
                        ids.append(doc_id)
                        docs.append(chunk)
                        metas.append({"fonte": pdf.name, "pagina": i + 1})
            # Inserção em lotes: gerar embeddings em lote é muito mais rápido que um por um
            for k in range(0, len(ids), lote):
                col.add(ids=ids[k:k + lote], documents=docs[k:k + lote], metadatas=metas[k:k + lote])
            if ids:
                print(f"[RAG] {pdf.name}: {len(ids)} trechos indexados", file=sys.stderr)
        except Exception as e:
            # stderr: no transporte stdio do MCP o stdout é reservado ao protocolo
            print(f"[RAG] erro ao indexar {pdf.name}: {e}", file=sys.stderr)


def _chunkar(texto: str, tam: int, overlap: int) -> list[str]:
    chunks, inicio = [], 0
    while inicio < len(texto):
        fim = inicio + tam
        chunks.append(texto[inicio:fim])
        inicio += tam - overlap
    return [c for c in chunks if len(c.strip()) > 50]


def buscar_documentos(consulta: str, n_resultados: int = 4) -> list[dict]:
    """
    Busca trechos relevantes na base de conhecimento.
    Retorna lista com texto e fonte de cada trecho.
    """
    try:
        col = _get_collection()
        if col.count() == 0:
            return [{"texto": "Base de conhecimento vazia. Rode scripts/baixar_documentos.py primeiro.", "fonte": ""}]
        res = col.query(query_texts=[consulta], n_results=min(n_resultados, col.count()))
        return [
            {"texto": doc, "fonte": meta.get("fonte", ""), "pagina": meta.get("pagina", "")}
            for doc, meta in zip(res["documents"][0], res["metadatas"][0])
        ]
    except Exception as e:
        return [{"texto": f"Erro no RAG: {e}", "fonte": ""}]
