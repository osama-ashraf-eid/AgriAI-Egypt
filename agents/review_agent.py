"""
review_agent.py — Reviews + Farmer ratings agent (كان مش موجود).
"""
import asyncio
from llm.llm_client import get_llm_client
from llm.prompt_builder import build_prompt
from rag.pipeline import get_pipeline, NO_CONTEXT_MESSAGE
from utils.logger import get_logger

logger = get_logger(__name__)


class ReviewAgent:
    def __init__(self):
        self.llm      = get_llm_client()
        self.pipeline = get_pipeline()

    async def process(self, message: str, clean_query: str, keywords: list[str], **kwargs) -> dict:
        try:
            # ابحث في reviews + farmers في آن واحد
            results, context = await asyncio.to_thread(
                self.pipeline.query,
                clean_query=clean_query,
                keywords=keywords,
                doc_types=["review", "farmer"],
                top_k=10,
                governorate=kwargs.get("governorate_filter"),
                use_reranker=True,
                intent="review",
            )

            # لو ما لقيناش تقييمات، نبحث في الـ farmers بس
            if not results:
                results, context = await asyncio.to_thread(
                    self.pipeline.query,
                    clean_query=clean_query,
                    keywords=keywords,
                    doc_types=["farmer"],
                    top_k=5,
                    governorate=kwargs.get("governorate_filter"),
                    intent="review",
                )
        except Exception as e:
            logger.error("review_agent.retrieval_failed", error=str(e))
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
            logger.error("review_agent.llm_failed", error=str(e))
            reply = "🚨 معلش يا غالي، حصل ضغط على سيرفر التقييمات، جرب تاني حالاً."

        logger.info("review_agent.done", sources=len(results))
        return {"reply": reply, "sources_count": len(results)}
