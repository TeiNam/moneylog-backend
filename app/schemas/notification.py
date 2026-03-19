"""
알림(Notification) 관련 Pydantic 요청/응답 스키마.

알림 조회, 읽음 처리 등
알림 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import UTCDatetimeResponse


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class NotificationResponse(UTCDatetimeResponse):
    """알림 응답 스키마."""

    id: UUID
    user_id: UUID
    subscription_id: UUID
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
