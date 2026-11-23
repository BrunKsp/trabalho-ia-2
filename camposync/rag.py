"""
Módulo RAG: indexa PDFs da pasta data/documentos/ e retorna trechos relevantes.

Na primeira execução cria o índice em data/chroma_db/.
Dependências: pip install chromadb pypdf sentence-transformers
"""
import os, hashlib
from pathlib import Path

from .config import DOCS_DIR, CHROMA_DIR

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    ef = DefaultEmbeddingFunction()
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = client.get_or_create_collection("safra_docs", embedding_function=ef)

    # Indexa PDFs ainda não indexados
    if DOCS_DIR.exists():
        _indexar_novos(_collection)

    return _collection


def _indexar_novos(col):
    from pypdf import PdfReader

    ids_existentes = set(col.get(include=[])["ids"])
    for pdf in DOCS_DIR.glob("*.pdf"):
        try:
            reader = PdfReader(str(pdf))
            for i, page in enumerate(reader.pages):
                texto = page.extract_text() or ""
                if len(texto.strip()) < 50:
                    continue
                # Divide em chunks de ~500 chars com overlap de 100
                chunks = _chunkar(texto, 500, 100)
                for j, chunk in enumerate(chunks):
                    doc_id = hashlib.md5(f"{pdf.name}_{i}_{j}".encode()).hexdigest()
                    if doc_id not in ids_existentes:
                        col.add(
                            ids=[doc_id],
                            documents=[chunk],
                            metadatas=[{"fonte": pdf.name, "pagina": i + 1}],
                        )
        except Exception as e:
            print(f"[RAG] erro ao indexar {pdf.name}: {e}")


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
