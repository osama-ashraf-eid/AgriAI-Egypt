"""
models/requests.py — Pydantic Request Schemas (FastAPI Gateway)
===============================================================
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

# 🎯 تحديد النطاق الصارم لأنواع بيانات المنصة المسموح بفهرستها
RAGDataType = Literal["products", "auctions", "orders", "reviews", "users"]


class ChatRequest(BaseModel):
    """الموديل الرسمي النظيف والآمن لطلبات الشات (مؤمن ومفصول عن حقول الهوية)"""
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=1000, 
        strip_whitespace=True, # 🎯 تنظيف تلقائي للمسافات الزائدة لمنع تشويه الـ Tokenizer
        description="سؤال المستخدم بالعامية التجارية المصرية"
    )
    governorate_filter: Optional[str] = Field(
        default=None, 
        strip_whitespace=True,
        description="فلتر جغرافي اختياري لتقييد البحث على مستوى المحافظة"
    )
    category_filter: Optional[str] = Field(
        default=None, 
        strip_whitespace=True,
        description="فلتر اختياري لتقييد المحاصيل حسب تصنيف القسم (Category ID)"
    )


class RAGIngestRequest(BaseModel):
    """موديل طلب الفهرسة وحقن البيانات (محصن ضد الأشكال العشوائية)"""
    data_types: List[RAGDataType] = Field(
        default=["products", "auctions", "orders", "reviews", "users"],
        description="قائمة قطاعات البيانات المسموح بحقنها في الـ Vector Store"
    )
    force_rebuild: bool = Field(
        default=False,
        description="تفعيل المسح الشامل وإعادة البناء الصفرية للفهرس لمنع التكرار"
    )


class RAGSearchRequest(BaseModel):
    """موديل طلب البحث المباشر في قاعدة البيانات المتجهية"""
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=500, 
        strip_whitespace=True,
        description="نص الاستعلام المراد البحث عنه"
    )
    top_k: int = Field(
        default=5, 
        ge=1, 
        le=20,
        description="عدد الوثائق المسترجعة الأعلى تشابهاً رياضياً"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="مصفوفة الفلاتر الإضافية (Metadata Where Clause)"
    )