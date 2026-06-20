"""
query_analyzer.py — LLM-based query analysis with multi-intent support.
"""
import json
import re
from llm.llm_client import get_llm_client
from rag.arabic_utils import normalize_arabic
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_INSTRUCTIONS = """أنت محرك تحليل استعلامات لمنصة "تعاوني" الزراعية المصرية.
مهمتك تحليل سؤال المستخدم وإخراج JSON نقي بالهيكل التالي حصراً:

{
  "original_query": "سؤال المستخدم كما هو",
  "keywords": ["كلمات_مفتاحية_صافية"],
  "entities": {
    "governorate": "اسم المحافظة إن وجد أو ''",
    "order_id": "رقم الطلب إن وجد أو ''",
    "farmer_name": "اسم المزارع إن وجد أو ''"
  },
  "intents": ["intent1", "intent2"],
  "intent": "الـ intent الأهم",
  "clean_query": "الهدف الصافي للبحث المتجهي"
}

## قائمة الـ intents المتاحة:
- marketplace : منتجات، أسعار، محاصيل، عروض، مزارعين
- auction     : مزادات، مزايدات، فائزون، خاسرون، أسعار المزايدة
- order       : طلبات، شحنات، توصيل، سائق، دفع
- review      : تقييمات المزارعين، نجوم، أحسن مزارع، آراء المشترين
- aggregation : أي سؤال إحصائي (كام، عدد، أعلى، أقل، أفضل، أرخص، أغلى)
- platform_help : طريقة استخدام المنصة، إرشادات
- memory_recall : المستخدم يسأل عن سياق المحادثة السابقة
- general_chat  : تحية أو كلام عام

## مهم جداً:
- لو السؤال يجمع أكتر من موضوع، اذكرهم كلهم في "intents"
- مثال: "احسن مزارعين وتقييماتهم" → intents: ["review", "aggregation"]
- مثال: "مين فاز بالمزاد وفيه بطاطس؟" → intents: ["auction", "marketplace"]
- ممنوع أي نص خارج الـ JSON"""


class QueryAnalyzer:
    def __init__(self):
        self.client = get_llm_client()

    async def analyze_query(self, message: str, chat_history_str: str = "") -> dict:
        user_input = f"""سياق المحادثة السابقة:
{chat_history_str or 'لا يوجد سياق سابق'}

سؤال المستخدم الحالي: {message}
أخرج الـ JSON الصافي مباشرة:"""

        try:
            full_prompt = f"{SYSTEM_INSTRUCTIONS}\n\n{user_input}"
            raw = await self.client.complete(full_prompt, temperature=0.0, max_tokens=400)

            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise ValueError("No JSON found")

            analysis = json.loads(match.group(0).strip())

            # ── normalize intents ──
            intents = analysis.get("intents", [])
            if not intents:
                intents = [analysis.get("intent", "marketplace")]
            analysis["intents"] = intents
            analysis["intent"]  = intents[0]

            # ── normalize clean_query ──
            if analysis.get("clean_query"):
                analysis["clean_query"] = normalize_arabic(analysis["clean_query"])
            else:
                analysis["clean_query"] = self._heuristic_clean(message)

            return analysis

        except Exception as e:
            logger.error("query_analyzer.failed", error=str(e))
            clean = self._heuristic_clean(message)
            return {
                "original_query": message,
                "keywords": [clean],
                "entities": {"governorate": "", "order_id": "", "farmer_name": ""},
                "intents":  ["marketplace"],
                "intent":   "marketplace",
                "clean_query": clean,
            }

    @staticmethod
    def _heuristic_clean(text: str) -> str:
        normalized = normalize_arabic(text)
        stop_words = {
            "موجود", "في", "منصه", "تعاوني", "ولا", "لا", "هو", "فيه",
            "دلوقتي", "متاح", "عندكم", "من", "هل", "ايه", "اي", "على",
            "عن", "بتاع", "بتاعت", "اللي", "ده", "دي", "دول"
        }
        words = [w for w in normalized.split() if w not in stop_words and len(w) > 2]
        return " ".join(words) if words else normalized
