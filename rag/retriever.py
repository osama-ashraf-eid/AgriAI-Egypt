"""
retriever.py — Hybrid retrieval: Dense (Chroma) + Sparse (BM25) + RRF fusion + Reranker.
"""
from rank_bm25 import BM25Okapi
from config import settings
from rag.vector_store import get_vector_store
from rag.reranker import rerank
from rag.arabic_utils import normalize_arabic
from utils.logger import get_logger

logger = get_logger(__name__)

_bm25_corpus: list[dict] = []
_bm25_index: BM25Okapi | None = None


def _eval_chroma_where(metadata: dict, where: dict | None) -> bool:
    """تقييم فلاتر Chroma على الـ BM25 corpus بدون كراش."""
    if not where:
        return True

    if "$and" in where:
        return all(_eval_chroma_where(metadata, clause) for clause in where["$and"])
    if "$or" in where:
        return any(_eval_chroma_where(metadata, clause) for clause in where["$or"])

    for key, value in where.items():
        if key.startswith("$"):
            continue
        if isinstance(value, dict):
            op = list(value.keys())[0]
            v  = list(value.values())[0]
            meta_val = str(metadata.get(key, ""))
            str_v    = str(v)
            if op == "$eq" and meta_val != str_v:
                return False
            if op == "$ne" and meta_val == str_v:
                return False
        else:
            if str(metadata.get(key, "")) != str(value):
                return False

    return True


def update_bm25_corpus(documents: list[dict]):
    global _bm25_corpus, _bm25_index
    _bm25_corpus = documents
    tokenized    = [normalize_arabic(d["text"]).split() for d in documents]
    _bm25_index  = BM25Okapi(tokenized)
    logger.info("retriever.bm25_updated", corpus_size=len(documents))


def _bm25_search(keywords: list[str], top_k: int, where: dict | None = None) -> list[dict]:
    if _bm25_index is None or not _bm25_corpus:
        return []

    tokens = [normalize_arabic(kw) for kw in keywords if kw.strip()]
    if not tokens:
        return []

    scores  = _bm25_index.get_scores(tokens)
    results = []

    for idx, score in enumerate(scores):
        if score <= 0:
            continue
        doc = _bm25_corpus[idx]
        if not _eval_chroma_where(doc.get("metadata", {}), where):
            continue
        results.append({
            "text":     doc["text"],
            "metadata": doc["metadata"],
            "score":    round(float(score), 4),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    for rank, r in enumerate(results[:top_k], start=1):
        r["bm25_rank"] = rank

    return results[:top_k]


def _rrf_fusion(dense: list[dict], bm25: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion لدمج نتائج الـ dense و BM25."""
    scores: dict[str, float] = {}
    docs:   dict[str, dict]  = {}

    for rank, doc in enumerate(dense, start=1):
        key = doc["text"][:250]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        docs[key]   = doc

    for rank, doc in enumerate(bm25, start=1):
        key = doc["text"][:250]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in docs:
            docs[key] = doc

    merged = sorted(docs.values(), key=lambda d: scores[d["text"][:250]], reverse=True)
    return merged


def retrieve(
    query: str,
    keywords: list[str] = None,
    top_k: int | None = None,
    where: dict | None = None,
    use_reranker: bool = True,
    min_score: float | None = None,
) -> list[dict]:
    top_k   = top_k or settings.RERANK_TOP_K
    fetch_k = settings.RETRIEVAL_TOP_K
    store   = get_vector_store()

    if keywords is None:
        keywords = [w for w in normalize_arabic(query).split() if len(w) > 2]

    dense_results = store.search(query=query, top_k=fetch_k, where=where)
    bm25_results  = _bm25_search(keywords=keywords, top_k=fetch_k, where=where)
    fused         = _rrf_fusion(dense_results, bm25_results, k=60)

    if use_reranker and fused:
        return rerank(query=query, results=fused, top_k=top_k, min_score=min_score)

    return fused[:top_k]
