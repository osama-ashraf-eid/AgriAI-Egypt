"""
auction_agent.py — Auctions + bids (winners & losers).
"""
import asyncio
from llm.llm_client import get_llm_client
from llm.prompt_builder import build_prompt
from rag.pipeline import get_pipeline, NO_CONTEXT_MESSAGE
from utils.logger import get_logger

logger = get_logger(__name__)


class AuctionAgent:
    def __init__(self):
        self.llm      = get_llm_client()
        self.pipeline = get_pipeline()

    async def process(self, message: str, clean_query: str, keywords: list[str], **kwargs) -> dict:
        gov = kwargs.get("governorate_filter")
        try:
            # بندور في auctions + bids في آن واحد
            results, context = await asyncio.to_thread(
                self.pipeline.query,
                clean_query=clean_query,
                keywords=keywords,
                doc_types=["auction", "bid"],
                top_k=10,
                governorate=gov,
                use_reranker=True,
                intent="auction",
            )

            if not results:
                results, context = await asyncio.to_thread(
                    self.pipeline.query,
                    clean_query=clean_query,
                    keywords=keywords,
                    doc_types=["auction", "bid", "product"],
                    top_k=8,
                    governorate=gov,
                    intent="auction",
                )
        except Exception as e:
            logger.error("auction_agent.retrieval_failed", error=str(e))
            results, context = [], NO_CONTEXT_MESSAGE

        prompt = build_prompt(
            query=message,
            context=context,
            user_role=kwargs.get("user_role", "trader"),
            chat_history=kwargs.get("chat_history"),
            intent="auction",
        )

        try:
            reply = await self.llm.complete(prompt, max_tokens=1024, temperature=0.3)
        except Exception as e:
            logger.error("auction_agent.llm_failed", error=str(e))
            reply = "🚨 يا غالي، حصل ضغط سريع على سيرفر المزادات، جرب تاني حالاً."

        logger.info("auction_agent.done", sources=len(results))
        return {"reply": reply, "sources_count": len(results)}
