import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from agents.supervisor import get_supervisor_agent
from utils.logger import get_logger
from utils.security import get_current_user
from memory.session_store import get_session_store

logger = get_logger(__name__)
router = APIRouter()


class PureMessageChatRequest(BaseModel):
    message: str = Field(..., description="سؤال المستخدم باللغة الطبيعية")


@router.post("/chat")
async def secure_message_only_endpoint(
    body: PureMessageChatRequest,
    current_user: dict = Depends(get_current_user)
):
    supervisor = get_supervisor_agent()
    store = get_session_store()
    
    user_id = current_user.get("user_id")
    user_role = current_user.get("role", "trader")

    # 🎯 استدعاء ديناميكي آمن وموحد لأحدث سيشن نشطة للمستخدم
    active_session_id = store.get_active_session(user_id)

    # إذا كانت الجلسة فارغة أو أول مرة يفتح الشات، قم بإنشاء جلسة جديدة وحفظها
    if not active_session_id:
        active_session_id = str(uuid.uuid4())
        logger.info("chat.mapping_new_session_to_user", user_id=user_id, session_id=active_session_id)
        store.set_active_session(user_id, active_session_id)

    try:
        response = await supervisor.process(
            message=body.message,
            user_id=user_id,
            user_role=user_role,
            session_id=active_session_id,
            governorate_filter=None,
            category_filter=None
        )
        response["session_id"] = active_session_id
        return response
        
    except Exception as e:
        logger.error("chat.secure_endpoint_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Secure RAG Error: {str(e)}"
        )