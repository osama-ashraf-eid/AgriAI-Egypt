"""
order_agent.py — Orders + logistics. No mandatory user filter for general queries.
"""
import asyncio
from llm.llm_client import get_llm_client
from llm.prompt_builder import build_prompt
from rag.pipeline import get_pipeline, NO_CONTEXT_MESSAGE
from utils.logger import get_logger

logger = get_logger(__name__)


class OrderAgent:
    def __init__(self):
        self.llm      = get_llm_client()
        self.pipeline = get_pipeline()

    async def process(self, message: str, clean_query: str, keywords: list[str], **kwargs) -> dict:
        user_role = kwargs.get("user_role", "trader")
        user_id   = kwargs.get("user_id", "")
        entities  = kwargs.get("entities", {})

        # ── فلتر الأمان: نبني extra_filters فقط لو في order_id محدد ──
        # لأن الفلتر بـ buyer_id كان بيمنع الأسئلة العامة عن الأوردرات
        extra_filters = {}
        if entities.get("order_id"):
            extra_filters["id"] = entities["order_id"]

        # لو المستخدم سأل عن أوردره الشخصي بشكل صريح، نضيف الفلتر
        personal_kw = ["طلبي", "أوردري", "أوردراتي", "طلباتي", "شحنتي", "أنا", "بتاعي"]
        is_personal = any(kw in message for kw in personal_kw)
        if is_personal and user_id:
            owner_field = "farmer_id" if user_role == "farmer" else "buyer_id"
            extra_filters[owner_field] = user_id

        try:
            results, context = await asyncio.to_thread(
                self.pipeline.query,
                clean_query=clean_query,
                keywords=keywords,
                doc_type="order",
                extra_filters=extra_filters or None,
                top_k=8,
                use_reranker=True,
                intent="order",
            )

            if not results:
                context = "لا توجد طلبات تطابق بحثك حالياً في قاعدة البيانات."
        except Exception as e:
            logger.error("order_agent.retrieval_failed", error=str(e))
            results, context = [], "لا توجد طلبات تطابق بحثك حالياً في قاعدة البيانات."

        prompt = build_prompt(
            query=message,
            context=context,
            user_role=user_role,
            chat_history=kwargs.get("chat_history"),
            intent="order",
        )

        try:
            reply = await self.llm.complete(prompt, max_tokens=1024, temperature=0.3)
        except Exception as e:
            logger.error("order_agent.llm_failed", error=str(e))
            reply = "🚨 يا زعيم، حصل ضغط سريع على سيرفر اللوجستيات، جرب تاني حالاً."

        logger.info("order_agent.done", user_id=user_id, sources=len(results))
        return {"reply": reply, "sources_count": len(results)}
