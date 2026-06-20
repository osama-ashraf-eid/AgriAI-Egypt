"""
models/responses.py — Pydantic Response Schemas (FastAPI Output Validation)
===========================================================================
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatResponse(BaseModel):
    """النموذج الموحد لردود الشات الذكية في منصة تعاوني"""
    reply: str = Field(
        ..., 
        description="الرد النهائي الصافي المصاغ بالعامية المصرية التجارية"
    )
    intent: str = Field(
        ..., 
        description="النية المكتشفة التي تم توجيه السؤال بناءً عليها (marketplace, auction, order...)"
    )
    sources_count: int = Field(
        ..., 
        description="عدد الوثائق أو السجلات العلاقاتية التي تم الاستناد إليها لبناء الرد"
    )
    session_id: str = Field(
        ..., 
        description="معرف الجلسة النشطة (UUID) للحفاظ على سياق الذاكرة الممتد"
    )


class RAGIngestResponse(BaseModel):
    """نموذج تأكيد نجاح عملية حقن وفهرسة البيانات"""
    status: str = Field(
        ..., 
        description="حالة العملية التجارية (success أو failed)"
    )
    documents_indexed: int = Field(
        ..., 
        description="إجمالي عدد الوثائق والسجلات التي تم تشفيرها وحقنها بنجاح"
    )
    message: str = Field(
        ..., 
        description="رسالة توضيحية تفصيلية لنوع البيانات ومصدرها"
    )


class RAGSearchResponse(BaseModel):
    """نموذج نتائج البحث المباشر في الفهرس المتجهي للـ RAG"""
    results: List[Dict[str, Any]] = Field(
        ..., 
        description="قائمة كتل النصوص المسترجعة مع الميتاداتا ونقاط التشابه الرياضي"
    )
    query: str = Field(
        ..., 
        description="نص الاستعلام الأصلي بعد التنظيف والمعالجة"
    )
    total_found: int = Field(
        ..., 
        description="عدد الوثائق الإجمالية التي تخطت عتبة القبول (Threshold)"
    )
    top_score: Optional[float] = Field(
        default=None, 
        description="أعلى نتيجة تقييم (Rerank Score) تم قنصها في البحث"
    )
    has_reliable_results: bool = Field(
        default=True, 
        description="مؤشر يوضح ما إذا كانت النتائج موثوقة وتخطت الحدود الآمنة للدرجات"
    )


class HealthResponse(BaseModel):
    """نموذج تقرير الفحص الصحي والمراقبة اللحظية للسيرفر"""
    status: str = Field(
        ..., 
        description="الحالة التشغيلية العامة للسيستم (ok)"
    )
    llm_loaded: bool = Field(
        ..., 
        description="مؤشر جاهزية واستقرار اتصال محرك الـ LLM Rotator"
    )
    embedder_loaded: bool = Field(
        ..., 
        description="مؤشر تحميل نموذج الـ Embeddings محلياً على السيرفر"
    )
    vector_store_docs: int = Field(
        ..., 
        description="العدد اللحظي الحالي للوثائق المخزنة داخل الـ Vector DB"
    )
    data_source: str = Field(
        ..., 
        description="نوع مصدر البيانات الحالي المربوط عليه السيستم (fake أو real)"
    )