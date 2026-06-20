"""
main.py — FastAPI entry point (production-ready for HuggingFace Spaces).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import settings
from utils.logger import get_logger
from utils.security import limiter
from api import chat, rag, health

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", app=settings.APP_NAME, data_mode="fake" if settings.USE_FAKE_DATA else "real")

    # ── تحميل النماذج ──
    from llm.llm_client import get_llm_client
    from rag.embedder   import get_embedder
    from rag.reranker   import get_reranker
    from rag.pipeline   import get_pipeline

    logger.info("loading.llm_client")
    get_llm_client()

    logger.info("loading.embedder")
    get_embedder()

    logger.info("loading.reranker")
    get_reranker()

    # ── بناء الـ Vector Store مع العلاقات الكاملة ──
    try:
        logger.info("startup.ingesting_all_data")
        pipeline = get_pipeline()
        counts   = await pipeline.ingest_all(force_rebuild=True)
        logger.info("startup.ingest_done", counts=counts)
    except Exception as e:
        logger.error("startup.ingest_failed", error=str(e))

    # ── تحميل دليل المنصة (FAQ) ──
    try:
        logger.info("startup.loading_faq_index")
        from utils.faq_retriever import EnterpriseFAQRetriever
        EnterpriseFAQRetriever()
        logger.info("startup.faq_ready")
    except Exception as e:
        logger.error("startup.faq_failed", error=str(e))

    logger.info("startup.all_ready")
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Taawuny AI — Agricultural RAG",
    description="نظام RAG ذكي لمنصة تعاوني الزراعية المصرية",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(chat.router,   prefix="/api/v1", tags=["Chat"])
app.include_router(rag.router,    prefix="/api/v1", tags=["RAG"])


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Taawuny AI RAG",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }
