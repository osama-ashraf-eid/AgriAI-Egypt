"""
marketplace_agent.py — Handles product search + farmer lookups.
"""
import asyncio
from llm.llm_client import get_llm_client
from llm.prompt_builder import build_prompt
from rag.pipeline import get_pipeline, NO_CONTEXT_MESSAGE
from utils.logger import get_logger

logger = get_logger(__name__)


class MarketplaceAgent:
    def __init__(self):
        self.llm      = get_llm_client()
        self.pipeline = get_pipeline()

    async def process(self, message: str, clean_query: str, keywords: list[str], **kwargs) -> dict:
        extra_filters = {}
        if kwargs.get("category_filter"):
            extra_filters["category_id"] = kwargs["category_filter"]

        # اجلب المزارعين والمنتجين برضه لو كان الـ intent يتعلق بمزارع بعينه
        entities = kwargs.get("entities", {})
        farmer_name_hint = entities.get("farmer_name", "")

        try:
            current_count = await asyncio.to_thread(self.pipeline.store.count)
            # top_k ديناميكي: ثلثين الـ corpus بحد أدنى 5 وأقصى 20
            dynamic_top_k = max(5, min(int(current_count * 0.65), 20))

            # ابحث في المنتجات أولاً
            results, context = await asyncio.to_thread(
                self.pipeline.query,
                clean_query=clean_query,
                keywords=keywords,
                doc_type="product",
                top_k=dynamic_top_k,
                governorate=kwargs.get("governorate_filter"),
                extra_filters=extra_filters or None,
                intent="marketplace",
            )

            # لو ما لقيناش نتائج، نبحث في الـ farmers برضه
            if not results:
                results_f, context_f = await asyncio.to_thread(
                    self.pipeline.query,
                    clean_query=clean_query,
                    keywords=keywords,
                    doc_type="farmer",
                    top_k=5,
                    governorate=kwargs.get("governorate_filter"),
                    intent="marketplace",
                )
                if results_f:
                    results, context = results_f, context_f

        except Exception as e:
            logger.error("marketplace_agent.retrieval_failed", error=str(e))
            results, context = [], NO_CONTEXT_MESSAGE

        prompt = build_prompt(
            query=message,
            context=context,
            user_role=kwargs.get("user_role", "trader"),
            chat_history=kwargs.get("chat_history"),
            intent="marketplace",
        )

        try:
            reply = await self.llm.complete(prompt, max_tokens=1024, temperature=0.3)
        except Exception as e:
            logger.error("marketplace_agent.llm_failed", error=str(e))
            reply = "🚨 معلش يا غالي، حصل ضغط سريع على السيرفر، جرب تاني حالاً."

        logger.info("marketplace_agent.done", sources=len(results))
        return {"reply": reply, "sources_count": len(results)}
