"""
경조사 인물(CeremonyPerson) 관련 Pydantic 응답 스키마.

경조사 인물 목록 조회, 검색 등
경조사 인물 API에서 사용하는 응답 모델을 정의한다.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class CeremonyPersonResponse(BaseModel):
    """경조사 인물 응답 스키마."""

    id: UUID
    user_id: UUID
    name: str
    relationship: str
    total_sent: int
    total_received: int
    event_count: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
