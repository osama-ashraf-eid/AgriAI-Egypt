import asyncio
from fastapi import APIRouter, Request
from config import settings
from models.requests import RAGIngestRequest, RAGSearchRequest
from models.responses import RAGIngestResponse, RAGSearchResponse
from rag.pipeline import get_pipeline
from rag.arabic_utils import normalize_arabic
from utils.security import limiter
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/rag/ingest", response_model=RAGIngestResponse)
@limiter.limit("5/minute")
async def ingest(request: Request, body: RAGIngestRequest):
    pipeline = get_pipeline()

    if body.force_rebuild or set(body.data_types) == {
        "products", "auctions", "orders", "reviews", "users"
    }:
        total = await pipeline.ingest_all(force_rebuild=body.force_rebuild)
    else:
        total = 0
        for data_type in body.data_types:
            total += await pipeline.ingest_by_type(data_type)

    logger.info("rag.ingest_completed", total_docs=total, types=body.data_types)

    return RAGIngestResponse(
        status="success",
        documents_indexed=total,
        message=f"تم فهرسة {total} وثيقة بنجاح من {'Fake Data' if settings.USE_FAKE_DATA else 'Real API'}",
    )


@router.post("/rag/search", response_model=RAGSearchResponse)
@limiter.limit("30/minute")
async def search(request: Request, body: RAGSearchRequest):
    pipeline = get_pipeline()

    where_clause = None
    if body.filters:
        cleaned_filters = {
            k: v for k, v in body.filters.items()
            if k != "additionalProp1" and v != {} and v is not None
        }
        if cleaned_filters:
            where_clause = cleaned_filters

    words_tokens = [w for w in normalize_arabic(body.query).split() if len(w) > 2]

    # 🎯 طوق النجاة الحاسم: تحويل الـ CPU-Bound Call لـ ThreadPool منفصل لضمان طيران السيرفر
    results, _ = await asyncio.to_thread(
        pipeline.query,
        clean_query=normalize_arabic(body.query),
        keywords=words_tokens,
        top_k=body.top_k,
        extra_filters=where_clause,
    )

    top_score = results[0]["rerank_score"] if results else None

    return RAGSearchResponse(
        results=results,
        query=body.query,
        total_found=len(results),
        top_score=top_score,
        has_reliable_results=len(results) > 0,
    )