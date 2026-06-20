from functools import lru_cache
import torch
from FlagEmbedding import FlagReranker
from config import settings
from rag.arabic_utils import normalize_arabic
from utils.logger import get_logger

logger = get_logger(__name__)

MIN_RERANK_SCORE_FALLBACK = 0.10

@lru_cache(maxsize=1)
def get_reranker() -> FlagReranker:
    # الفحص التلقائي لضمان عدم حدوث كراش على الـ CPU في Hugging Face
    use_fp16 = torch.cuda.is_available()
    return FlagReranker(settings.RERANKER_MODEL, use_fp16=use_fp16)

def rerank(query: str, results: list[dict], top_k: int = 5, min_score: float | None = None) -> list[dict]:
    if not results:
        return []

    min_score = settings.MIN_RERANK_SCORE if min_score is None else min_score
    reranker = get_reranker()

    normalized_query = normalize_arabic(query)
    pairs = [[normalized_query, r["text"]] for r in results]

    scores = reranker.compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        scores = [scores]

    for result, score in zip(results, scores):
        result["rerank_score"] = round(float(score), 4)

    ranked = sorted(results, key=lambda x: x["rerank_score"], reverse=True)
    filtered = [r for r in ranked if r["rerank_score"] >= min_score]

    if not filtered and ranked and ranked[0]["rerank_score"] >= MIN_RERANK_SCORE_FALLBACK:
        filtered = ranked[:1]
        logger.info("reranker.soft_fallback_triggered", top_score=ranked[0]["rerank_score"])

    logger.info("reranker.scored", candidates=len(ranked), kept_above_threshold=len(filtered))
    return filtered[:top_k]