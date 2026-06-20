import asyncio
from fastapi import APIRouter
from config import settings, get_data_source
from models.responses import HealthResponse
from rag.vector_store import get_vector_store

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    store = get_vector_store()
    
    # 🎯 تأمين الـ Disk I/O: تشغيل الـ count التزامني في خيط منفصل منعاً لتعطيل الـ Event Loop
    docs_count = await asyncio.to_thread(store.count)
    
    return HealthResponse(
        status="ok",
        llm_loaded=True,
        embedder_loaded=True,
        vector_store_docs=docs_count,
        data_source="fake" if settings.USE_FAKE_DATA else "real",
    )