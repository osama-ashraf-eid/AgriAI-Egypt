import uuid
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings
from .embedder import embed_texts, embed_query
from .transformer import Document

class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, documents: list[Document], batch_size: int = 100):
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            texts     = [d.text for d in batch]
            metadatas = [d.metadata for d in batch]
            ids       = [str(uuid.uuid4()) for _ in batch]
            embeddings = embed_texts(texts)

            self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids,
                )

    def search(self, query: str, top_k: int = 20, where: dict = None) -> list[dict]:
        query_embedding = embed_query(query)
        kwargs = dict(
            query_embeddings=[query_embedding],
            n_results=min(top_k, max(self.collection.count(), 1)),
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)
        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text":     doc,
                "metadata": meta,
                "score":    round(1 - dist, 4),
            })
        return output

    def delete_by_type(self, doc_type: str):
        self.collection.delete(where={"doc_type": doc_type})

    def clear_all(self):
        self.client.delete_collection(settings.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=settings.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self.collection.count()


_vector_store: VectorStore | None = None

def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store