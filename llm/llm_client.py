import os
import httpx
import asyncio
import itertools
from functools import lru_cache
from typing import List, Dict
from dotenv import load_dotenv
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

load_dotenv()

# توكنز التوقف الصارمة لضمان عبور الـ Request بأمان من فلاتر Groq
STOP_TOKENS = ["<|im_end|>", "المستخدم:"]


class LLMClient:
    def __init__(self):
        # 🎯 تقرأ الاسم بالجمع أو المفرد تلقائياً وتجيب السلسلة الكاملة
        raw_keys = os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_KEY") or ""
        
        # تقسيم السلسلة فوراً بناءً على الفواصل وتنظيف المسافات
        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        
        if not self.api_keys:
            logger.critical("llm.groq_keys_missing_fatal")
            self.key_cycle = None
        else:
            # إنشاء حلقة تدوير ذكية لا تنتهي للأكواد (Round Robin Engine)
            self.key_cycle = itertools.cycle(self.api_keys)

        self.api_url = settings.GROQ_API_URL or os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
        self.model_name = settings.LLM_MODEL_NAME or os.getenv("LLM_MODEL_NAME", "llama-3.3-70b-versatile")
        
        # 🎯 التعديل الإنتاجي الأول: إنشاء عميل Async موحد ومستمر لتفعيل الـ Connection Pooling وتسريع الاستجابة
        self.client = httpx.AsyncClient(timeout=20.0)
        
        logger.info("llm.initialized_groq_rotator", url=self.api_url, model=self.model_name, total_keys=len(self.api_keys) if self.api_keys else 0)

    async def complete(
        self,
        prompt: str | List[Dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE

        if not self.api_keys:
            logger.error("llm.groq_key_missing")
            return "🚨 يا هندسة، الـ API Keys واصلة للبايثون كـ (سلسلة فارغة) في الـ .env!"

        # 🎯 الفرز التلقائي بين النص العادي والهيكل الجاهز
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = prompt

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "stop": STOP_TOKENS
        }

        # 🎯 التعديل الإنتاجي الثاني: استبدال الـ print العادية بنظام الـ Logger الرسمي والنظيف للمنصة
        logger.debug("llm.groq_request_payload", payload=payload)

        # 🔄 لفة التدوير الدفاعي المتكاملة (تتحمل الـ 429 وأي خطأ شبكي عابر)
        for attempt in range(len(self.api_keys)):
            current_key = next(self.key_cycle)
            key_preview = f"{current_key[:8]}...{current_key[-4:]}" if len(current_key) > 12 else "Hidden"

            try:
                headers = {
                    "Authorization": f"Bearer {current_key}",
                    "Content-Type": "application/json"
                }

                # 🎯 التعديل الإنتاجي الثالث: استخدام العميل المستمر الموحد بدلاً من هدم وبناء العميل في كل لفة
                res = await self.client.post(self.api_url, headers=headers, json=payload)
                
                # 🎯 قنص الـ Rate Limits أو أي أخطاء سيرفر طارئة (502, 503, 504) لتفعيل الـ Failover فوراً
                if res.status_code in (429, 502, 503, 504):
                    logger.warning(
                        "llm.groq_retry_trigger_caught_activating_failover", 
                        status_code=res.status_code,
                        failed_key=key_preview, 
                        remaining_attempts=len(self.api_keys) - (attempt + 1)
                    )
                    await asyncio.sleep(0.1)  # تهدئة سريعة
                    continue  # القفز للمفتاح الاحتياطي التالي فوراً دون إفشال الـ Request
                    
                res.raise_for_status()
                res_data = res.json()
                return res_data["choices"][0]["message"]["content"].strip()

            except Exception as e:
                error_msg = str(e).lower()
                # التحقق الإضافي لو الخطأ جاي من داخل الـ Exception النصي ويحمل دلالات خطأ مؤقت
                if any(indicator in error_msg for indicator in ["429", "rate_limit", "too_many_requests", "timeout", "502", "503"]):
                    logger.warning(
                        "llm.groq_exception_failover_triggered", 
                        error=str(e),
                        failed_key=key_preview, 
                        remaining_attempts=len(self.api_keys) - (attempt + 1)
                    )
                    await asyncio.sleep(0.1)
                    continue
                
                # لو خطأ حقيقي قاتل في الـ Auth أو التركيب البنيوي، نسجله ونطير للمفتاح اللّي بعده برضه لضمان الأمان
                logger.error("llm.groq_individual_key_failed_trying_next", failed_key=key_preview, error=str(e))
                continue

        # لو اللفة بالكامل خلصت وكل الحسابات الاحتياطية الممررة مش قادرة تلبي المعاملة التجارية
        return "🚨 جميع مفاتيح Groq المسجلة غير متاحة حالياً أو ضربت الـ Limits في نفس الوقت! اِنتظر دقيقة للـ Cooldown."

    async def classify_intent(self, prompt: str | List[Dict[str, str]]) -> str:
        return await self.complete(prompt, max_tokens=10, temperature=0.0)


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return LLMClient()