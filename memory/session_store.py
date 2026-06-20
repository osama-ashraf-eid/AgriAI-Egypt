from functools import lru_cache
from utils.cache import get_cache
from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)


class SessionStore:
    def __init__(self):
        self.cache = get_cache()

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}:history"

    @staticmethod
    def _user_mapping_key(user_id: str) -> str:
        return f"user:{user_id}:active_session"

    def get_history(self, session_id: str) -> list[dict]:
        if not session_id:
            return []

        try:
            data = self.cache.get(self._key(session_id))
            # عمل نسخة نظيفة (Shallow Copy) لمنع الـ Reference Leaks في الـ Memory
            history = list(data.get("turns", [])) if data else []
            
            logger.info(
                "session_store.history_loaded",
                session_id=session_id,
                turns=len(history),
            )
            return history
        except Exception as e:
            # 🎯 طوق النجاة: لو سيرفر الكاش (Redis) وقع، سجل الخطأ ورجع مصفوفة فارغة لحماية الـ Request من الكراش
            logger.error("session_store.get_history_failed_cache_layer_down", session_id=session_id, error=str(e))
            return []

    def append_turn(self, session_id: str, role: str, content: str):
        if not session_id:
            return

        try:
            # قراءة التاريخ الحالي
            history = self.get_history(session_id)
            history.append({"role": role, "content": content})

            # لجام الذاكرة الموسعة تماشياً مع الـ Settings بتاعتك
            if len(history) > settings.SESSION_MAX_TURNS:
                history = history[-settings.SESSION_MAX_TURNS:]

            # الكتابة الآمنة في الكاش مع الـ TTL المحدد للمنصة
            self.cache.set(
                self._key(session_id),
                {"turns": history},
                ttl=settings.SESSION_TTL_SECONDS,
            )

            logger.info(
                "session_store.turn_appended",
                session_id=session_id,
                role=role,
                total_turns=len(history),
            )
        except Exception as e:
            # حماية الذاكرة من الـ Blind Overwrite في حالة الكراش المفاجئ لطبقة الكاش
            logger.error("session_store.append_turn_failed", session_id=session_id, error=str(e))

    def clear(self, session_id: str):
        if not session_id:
            return
        try:
            self.cache.delete(self._key(session_id))
            logger.info("session_store.cleared", session_id=session_id)
        except Exception as e:
            logger.error("session_store.clear_failed", session_id=session_id, error=str(e))

    # ── 🎯 دوال التتبع الديناميكي الموحدة لحفظ واسترجاع جلسة العميل الحالية ──
    def get_active_session(self, user_id: str) -> str | None:
        if not user_id:
            return None
        
        try:
            key = self._user_mapping_key(user_id)
            cached_data = self.cache.get(key)
            
            if cached_data:
                # معالجة مرنة لكافة صيغ الـ Serialization لمنع كراشات الـ Type Mismatch
                if isinstance(cached_data, dict) and "session_id" in cached_data:
                    return cached_data["session_id"]
                return str(cached_data)
            return None
        except Exception as e:
            logger.error("session_store.get_active_session_failed", user_id=user_id, error=str(e))
            return None

    def set_active_session(self, user_id: str, session_id: str):
        if not user_id or not session_id:
            return
            
        try:
            key = self._user_mapping_key(user_id)
            self.cache.set(key, session_id, ttl=settings.SESSION_TTL_SECONDS)
            logger.info("session_store.mapped_user_to_session", user_id=user_id, session_id=session_id)
        except Exception as e:
            logger.error("session_store.set_active_session_failed", user_id=user_id, session_id=session_id, error=str(e))


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    return SessionStore()