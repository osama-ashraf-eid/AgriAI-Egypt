"""
embedder.py — Singleton BGE-M3 embedder (CPU-safe for HuggingFace Spaces).
"""
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        logger.info("embedder.loading", model=settings.EMBEDDING_MODEL)
        _embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("embedder.ready")
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    return model.encode(texts, show_progress_bar=False, normalize_embeddings=True).tolist()


def embed_query(query: str) -> list[float]:
    model = get_embedder()
    return model.encode(query, show_progress_bar=False, normalize_embeddings=True).tolist()
