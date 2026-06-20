import json
import time
import hashlib
from collections import OrderedDict
from functools import lru_cache
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class _MemoryEntry:
    __slots__ = ("raw", "expires_at")

    def __init__(self, raw: str, ttl: int):
        self.raw = raw
        self.expires_at = time.monotonic() + ttl

    @property
    def expired(self) -> bool:
        return time.monotonic() > self.expires_at


class CacheService:
    def __init__(self):
        self._redis = None
        # 🎯 تحويل الكاش المحلي لـ OrderedDict لتطبيق آلية طرد محكومة السعة (LRU-like Eviction)
        self._memory_cache: OrderedDict[str, _MemoryEntry] = OrderedDict()
        self._max_memory_entries = 5000  # حد أمان صارم لمنع انفجار الذاكرة في الإنتاج

        try:
            import redis
            self._redis = redis.Redis.from_url(
                settings.REDIS_URL, 
                decode_responses=True, 
                socket_connect_timeout=1,
                retry_on_timeout=True  # إعادة المحاولة التلقائية عند حدوث بلب شبكي عابر
            )
            self._redis.ping()
            logger.info("cache.redis_connected")
        except Exception as e:
            logger.warning("cache.redis_unavailable_using_memory_fallback", error=str(e))
            self._redis = None

    @property
    def redis(self):
        return self._redis

    @staticmethod
    def make_key(*parts: str) -> str:
        raw = "|".join(parts)
        return "agriai:" + hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _evict(self):
        """تنظيف الكيز المنتهية الصلاحية من الذاكرة الاحتياطية"""
        dead = [k for k, v in self._memory_cache.items() if v.expired]
        for k in dead:
            self._memory_cache.pop(k, None)
        if dead:
            logger.debug("cache.evicted_expired_keys", count=len(dead))

    def get(self, key: str) -> dict | None:
        try:
            if self._redis:
                raw = self._redis.get(key)
                return json.loads(raw) if raw else None

            # نظام الـ Fallback المحلي
            entry = self._memory_cache.get(key)
            if entry is None:
                return None
            if entry.expired:
                self._memory_cache.pop(key, None)
                return None
            
            # تحديث مكان الكي في الـ OrderedDict لإنعاشه (تم إستخدامه مؤخراً)
            self._memory_cache.move_to_end(key)
            return json.loads(entry.raw)
        except Exception as e:
            logger.error("cache.get_failed", key=key, error=str(e))
            return None

    def set(self, key: str, value: dict, ttl: int | None = None):
        ttl = ttl or settings.CACHE_TTL_SECONDS
        try:
            raw = json.dumps(value, ensure_ascii=False)
            if self._redis:
                self._redis.set(key, raw, ex=ttl)
            else:
                self._evict()
                
                # 🎯 صمام الأمان: لو الكاش تخطى السعة المسموحة، اِطرد أقدم عنصر فوراً لحماية الـ RAM
                if len(self._memory_cache) >= self._max_memory_entries:
                    oldest_key, _ = self._memory_cache.popitem(last=False)
                    logger.debug("cache.memory_limit_reached_evicting_oldest", evicted_key=oldest_key)
                    
                self._memory_cache[key] = _MemoryEntry(raw, ttl)
        except Exception as e:
            logger.warning("cache.set_failed", key=key, error=str(e))

    def delete(self, key: str):
        try:
            if self._redis:
                self._redis.delete(key)
            else:
                self._memory_cache.pop(key, None)
        except Exception as e:
            logger.error("cache.delete_failed", key=key, error=str(e))


@lru_cache(maxsize=1)
def get_cache() -> CacheService:
    return CacheService()