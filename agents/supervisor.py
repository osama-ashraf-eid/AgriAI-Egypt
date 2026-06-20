"""
supervisor.py — Multi-intent router: يدور في أكتر من collection لو السؤال مركب.
"""
import asyncio
from enum import Enum
from functools import lru_cache
from rag.query_analyzer import QueryAnalyzer
from rag.arabic_utils import normalize_arabic
from utils.logger import get_logger
from memory.session_store import get_session_store

logger = get_logger(__name__)


class Intent(str, Enum):
    MARKETPLACE   = "marketplace"
    AUCTION       = "auction"
    ORDER         = "order"
    REVIEW        = "review"
    PLATFORM_HELP = "platform_help"
    MEMORY_RECALL = "memory_recall"
    AGGREGATION   = "aggregation"
    GENERAL       = "general_chat"


# ── خريطة: intent → doc_types اللي بندور فيها ──
INTENT_DOC_TYPES: dict[str, list[str]] = {
    "marketplace": ["product", "farmer"],
    "auction":     ["auction", "bid"],
    "order":       ["order"],
    "review":      ["review", "farmer"],
    "aggregation": [],          # بيتعمل بطريقة مختلفة
    "platform_help": [],
    "memory_recall": [],
    "general_chat": [],
}

# ── Keywords سريعة لتصنيف النوايا بدون LLM ──
_PLATFORM_KW = [
    "ازاي اضيف", "كيفية اضافة", "طريقة عمل مزاد", "ازاي اعمل مزاد",
    "اضيف محصول", "ابيع ازاي", "اشتري ازاي", "شرح المنصه",
    "تنزيل منتج", "كيفية استخدام", "اشحن", "المحفظه", "اسحب",
    "عموله", "الغاء طلب",
]

_AGGREGATION_KW = [
    "كام", "عدد", "عددهم", "إجمالي", "اجمالي", "مجموع", "متوسط",
    "أعلى", "اعلى", "أكثر", "اكثر", "أكبر", "اكبر",
    "أقل", "اقل", "أرخص", "ارخص", "أغلى", "اغلى",
    "إحصائ", "احصائ", "تحليل", "نسبة", "كم عدد",
    "احسن", "أحسن", "أفضل", "افضل",
]

_REVIEW_KW = [
    "تقييم", "تقييمات", "نجوم", "رأي", "آراء", "مرضي", "مش مرضي",
    "احسن مزارع", "أحسن مزارع", "أفضل مزارع",
]

_ORDER_KW = [
    "طلب", "اوردر", "أوردر", "شحنه", "توصيل", "سواق", "سائق",
    "مبعتش", "وصل", "متأخر", "تتبع", "دفع", "مدفوع",
]

_AUCTION_KW = [
    "مزاد", "مزايده", "مزايدة", "بيد", "فاز", "فايز", "فازوا",
    "خسر", "خاسر", "خاسرين", "مين فاز", "مين كسب",
]


def _fast_classify(msg: str) -> str | None:
    """تصنيف سريع بدون LLM لتوفير الـ tokens."""
    if any(kw in msg for kw in _PLATFORM_KW):
        return "platform_help"
    if any(kw in msg for kw in _AGGREGATION_KW):
        return "aggregation"
    if any(kw in msg for kw in _REVIEW_KW):
        return "review"
    if any(kw in msg for kw in _ORDER_KW):
        return "order"
    if any(kw in msg for kw in _AUCTION_KW):
        return "auction"
    return None


def _detect_multi_intent(msg: str, llm_intents: list[str]) -> list[str]:
    """
    يدمج التصنيف السريع مع ناتج الـ LLM عشان يطلع قائمة كاملة.
    مثال: "احسن مزارعين وتقييماتهم وكمان فيه أوردرات؟"
    → ["review", "farmer", "aggregation"]
    """
    detected = set(llm_intents)
    if any(kw in msg for kw in _REVIEW_KW):
        detected.add("review")
    if any(kw in msg for kw in _ORDER_KW):
        detected.add("order")
    if any(kw in msg for kw in _AUCTION_KW):
        detected.add("auction")
    return list(detected)


class SupervisorAgent:
    def __init__(self):
        self.analyzer = QueryAnalyzer()

    async def process(
        self,
        message: str,
        user_id: str,
        user_role: str,
        session_id: str = "",
        governorate_filter: str | None = None,
        category_filter: str | None = None,
        chat_history: list[dict] | None = None,
    ) -> dict:
        from llm.prompt_builder import build_prompt
        from utils.faq_retriever import retrieve_relevant_faqs
        from llm.llm_client import get_llm_client
        from rag.pipeline import get_pipeline

        # ── Session & history ──
        store         = get_session_store()
        clean_history = chat_history or []
        if not clean_history and session_id:
            clean_history = store.get_history(session_id)

        history_str = "\n".join(
            f"{'المستخدم' if t['role']=='user' else 'تعاوني'}: {t['content']}"
            for t in clean_history[-10:]
        )

        msg_norm = normalize_arabic(message)

        # ── 1. Fast-path heuristics ──
        fast_intent = _fast_classify(msg_norm)

        if fast_intent and fast_intent not in ("aggregation", "review"):
            # للـ platform_help, order, auction نروح مباشرة
            intent_value = fast_intent
            clean_query  = message
            keywords     = [w for w in msg_norm.split() if len(w) > 2]
            analysis     = {
                "intent": intent_value, "clean_query": message,
                "keywords": keywords, "entities": {}, "intents": [intent_value]
            }
        else:
            # ── 2. LLM analysis ──
            analysis     = await self.analyzer.analyze_query(message, history_str)
            intent_value = analysis.get("intent", "marketplace")
            clean_query  = analysis.get("clean_query", message)
            keywords     = analysis.get("keywords", [])
            llm_intents  = analysis.get("intents", [intent_value])

            # ── 3. Multi-intent detection ──
            all_intents = _detect_multi_intent(msg_norm, llm_intents)

            # Aggregation override
            if fast_intent == "aggregation":
                intent_value = "aggregation"
                all_intents  = ["aggregation"]

            analysis["all_intents"] = all_intents

        logger.info("supervisor.routing",
                    intent=intent_value,
                    all_intents=analysis.get("all_intents", [intent_value]))

        # ── 4. Execution ──
        faq_context = None

        if intent_value == "memory_recall":
            return await self._handle_memory_recall(
                message, user_role, clean_history, session_id, store
            )

        if intent_value == "platform_help":
            faq_context = await asyncio.to_thread(retrieve_relevant_faqs, message)
            if not faq_context:
                intent_value = "marketplace"   # fallback

        if intent_value == "platform_help" and faq_context:
            return await self._handle_platform_help(
                message, faq_context, user_role, clean_history, session_id, store
            )

        # ── 5. Extract geo entity ──
        extracted_gov  = (analysis.get("entities") or {}).get("governorate", "")
        final_gov      = governorate_filter or (extracted_gov if extracted_gov else None)

        kwargs = dict(
            message=message,
            clean_query=clean_query,
            keywords=keywords,
            user_id=user_id,
            user_role=user_role,
            governorate_filter=final_gov,
            category_filter=category_filter,
            chat_history=clean_history,
            entities=analysis.get("entities") or {},
            all_intents=analysis.get("all_intents", [intent_value]),
        )

        if intent_value == "aggregation":
            result = await self._handle_aggregation(message, user_role, clean_history, final_gov)

        elif intent_value in ("auction", "order", "review"):
            result = await self._handle_typed_agent(intent_value, **kwargs)

        else:
            # marketplace + multi-intent
            result = await self._handle_marketplace_multi(**kwargs)

        if session_id:
            store.append_turn(session_id, "user", message)
            store.append_turn(session_id, "assistant", result["reply"])

        result["intent"]     = intent_value
        result["session_id"] = session_id
        return result

    # ══════════════════════════════════════════════
    # Handlers
    # ══════════════════════════════════════════════

    async def _handle_memory_recall(self, message, user_role, history, session_id, store):
        from llm.prompt_builder import build_prompt
        from llm.llm_client import get_llm_client
        prompt = build_prompt(query=message, context="NO_CONTEXT",
                              user_role=user_role, chat_history=history, intent="memory_recall")
        llm    = get_llm_client()
        try:
            reply = await llm.complete(prompt, max_tokens=512, temperature=0.3)
        except Exception:
            reply = "🚨 الذاكرة خانتني للحظة، فكرني كنا بنقول إيه؟"
        if session_id:
            store.append_turn(session_id, "user", message)
            store.append_turn(session_id, "assistant", reply)
        return {"reply": reply, "sources_count": 0, "intent": "memory_recall", "session_id": session_id}

    async def _handle_platform_help(self, message, faq_ctx, user_role, history, session_id, store):
        from llm.prompt_builder import build_prompt
        from llm.llm_client import get_llm_client
        prompt = build_prompt(query=message, context=faq_ctx,
                              user_role=user_role, chat_history=history, intent="platform_help")
        llm    = get_llm_client()
        try:
            reply = await llm.complete(prompt, max_tokens=1024, temperature=0.3)
        except Exception:
            reply = "🚨 حصل ضغط على دليل المنصة، جرب تسأل تاني حالاً."
        if session_id:
            store.append_turn(session_id, "user", message)
            store.append_turn(session_id, "assistant", reply)
        return {"reply": reply, "sources_count": 1, "intent": "platform_help", "session_id": session_id}

    async def _handle_aggregation(self, message, user_role, history, governorate):
        from llm.prompt_builder import build_prompt
        from llm.llm_client import get_llm_client
        from rag.pipeline import get_pipeline
        pipeline          = get_pipeline()
        results, context  = await pipeline.query_analytics(governorate=governorate)
        prompt = build_prompt(query=message, context=context,
                              user_role=user_role, chat_history=history, intent="aggregation")
        llm    = get_llm_client()
        try:
            reply = await llm.complete(prompt, max_tokens=1024, temperature=0.2)
        except Exception:
            reply = "🚨 حصلت قفلة في سيرفر الحسابات، جرب تاني حالاً."
        return {"reply": reply, "sources_count": len(results)}

    async def _handle_typed_agent(self, intent: str, **kwargs):
        """auction / order / review"""
        from agents.auction_agent import AuctionAgent
        from agents.order_agent   import OrderAgent
        from agents.review_agent  import ReviewAgent

        if intent == "auction":
            return await AuctionAgent().process(**kwargs)
        if intent == "order":
            return await OrderAgent().process(**kwargs)
        if intent == "review":
            return await ReviewAgent().process(**kwargs)

    async def _handle_marketplace_multi(self, **kwargs):
        """
        بيجمع نتائج من أكتر من collection حسب all_intents.
        لو all_intents = ["marketplace", "review"] → بيدور في products + farmers + reviews
        """
        from llm.prompt_builder import build_prompt
        from llm.llm_client     import get_llm_client
        from rag.pipeline       import get_pipeline
        from rag.retriever      import retrieve

        all_intents = kwargs.get("all_intents", ["marketplace"])
        clean_query = kwargs["clean_query"]
        keywords    = kwargs.get("keywords", [])
        governorate = kwargs.get("governorate_filter")

        # جمع كل الـ doc_types المطلوبة
        all_doc_types = []
        for intent in all_intents:
            all_doc_types.extend(INTENT_DOC_TYPES.get(intent, ["product"]))
        all_doc_types = list(dict.fromkeys(all_doc_types))  # unique + ordered

        if not all_doc_types:
            all_doc_types = ["product", "farmer"]

        pipeline = get_pipeline()
        try:
            count         = await asyncio.to_thread(pipeline.store.count)
            dynamic_top_k = max(6, min(int(count * 0.5), 20))

            results, context = await asyncio.to_thread(
                pipeline.query,
                clean_query=clean_query,
                keywords=keywords,
                doc_types=all_doc_types,
                top_k=dynamic_top_k,
                governorate=governorate,
                use_reranker=True,
                intent="marketplace",
            )
        except Exception as e:
            logger.error("supervisor.multi_retrieval_failed", error=str(e))
            results, context = [], "NO_CONTEXT"

        prompt = build_prompt(
            query=kwargs["message"],
            context=context,
            user_role=kwargs.get("user_role", "trader"),
            chat_history=kwargs.get("chat_history"),
            intent="marketplace",
        )

        llm = get_llm_client()
        try:
            reply = await llm.complete(prompt, max_tokens=1024, temperature=0.3)
        except Exception as e:
            logger.error("supervisor.llm_failed", error=str(e))
            reply = "🚨 معلش يا غالي، حصل ضغط سريع على السيرفر، جرب تاني حالاً."

        return {"reply": reply, "sources_count": len(results)}


@lru_cache(maxsize=1)
def get_supervisor_agent() -> SupervisorAgent:
    return SupervisorAgent()
