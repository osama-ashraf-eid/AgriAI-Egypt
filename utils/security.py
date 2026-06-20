import re
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError, ExpiredSignatureError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import settings
from utils.logger import get_logger  # 🎯 تم إضافة الـ Import الناقص هنا

logger = get_logger(__name__)  # 🎯 تم تعريف اللوجر صراحة لحل المشكلة الأولى

limiter = Limiter(key_func=get_remote_address)

# تأمين الـ ReDoS: تبسيط وتجريد الأنماط لمنع الـ Catastrophic Backtracking القاتل للسيرفر
INJECTION_PATTERNS = [
    r"ignore.*instructions",
    r"disregard.*instructions",
    r"you are now",
    r"pretend you are",
    r"act as",
    r"jailbreak",
    r"dan mode",
    r"\n\n(system|assistant|user)\s*:",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"forget everything",
    r"تجاهل.*التعليمات",
    r"انت دلوقتي",
    r"تخيل انك",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def sanitize_input(text: str, max_len: int = 1000) -> str:
    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الرسالة لا يمكن أن تكون فارغة",
        )

    text = text[:max_len]

    # فحص الأنماط بـ الأوزان الأمنية المحمية
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            logger.warning("security.malicious_injection_blocked", input_preview=text[:50])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="تم رفض الطلب — محتوى غير مسموح به",  # 🎯 تم تبديل الفصلة العربي لإنجليزي لحل المشكلة الثانية
            )

    # تنظيف الـ Control Characters الملعونة من نصوص الـ UTF-8
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


ALGORITHM = "HS256"
security_scheme = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_minutes: int = 60) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TOKEN_EXPIRED",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز الدخول غير صالح أو تالف",
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="يرجى تسجيل الدخول أولاً وتوفير رمز الدخول (Token missing)",
        )
        
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id = payload.get("user_id") or payload.get("sub")
    role = payload.get("role") or payload.get("user_role") or "trader"
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز الدخول تالف ولا يحتوي على معرف مستخدم صالح",
        )
        
    return {
        "user_id": str(user_id),
        "role": str(role)
    }


def check_user_owns_resource(requesting_user_id: str, resource_owner_id: str):
    if requesting_user_id != resource_owner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح لك بالوصول لهذا المورد",
        )