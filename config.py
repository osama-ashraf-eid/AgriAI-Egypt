"""
config.py — Global Configuration (Pydantic Settings v2)
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # ── App ──
    APP_NAME: str = "Taawuny RAG"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    HF_HUB_DISABLE_SYMLINKS: str = "1"

    # ── LLM (Groq) ──
    GROQ_API_KEYS: str = ""
    GROQ_API_KEY: str = ""
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
    LLM_MODEL_NAME: str = "llama-3.3-70b-versatile"
    LLM_CTX_SIZE: int = 4096
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.25

    # ── RAG / Vector Store ──
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    COLLECTION_NAME: str = "taawuny_v2"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RETRIEVAL_TOP_K: int = 20
    RERANK_TOP_K: int = 6
    MIN_RERANK_SCORE: float = 0.08

    # ── Session / Memory ──
    SESSION_MAX_TURNS: int = 20
    SESSION_TTL_SECONDS: int = 3600

    # ── Data Source ──
    USE_FAKE_DATA: bool = True
    REAL_API_BASE_URL: str = "https://api.taawuny.com"
    REAL_API_KEY: str = ""

    # ── Cache / Rate Limit ──
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_SECONDS: int = 300
    RATE_LIMIT_CHAT: str = "30/minute"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def get_data_source():
    if settings.USE_FAKE_DATA:
        from data_sources.fake_source import FakeDataSource
        return FakeDataSource()
    from data_sources.real_source import RealApiDataSource
    return RealApiDataSource(
        base_url=settings.REAL_API_BASE_URL,
        api_key=settings.REAL_API_KEY,
    )
