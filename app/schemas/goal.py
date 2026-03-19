"""
목표(Goal) 관련 Pydantic 요청/응답 스키마.

목표 생성, 수정, 조회, 상세(진행률 포함) 등
목표 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import GoalType
from app.schemas.common import UTCDatetimeResponse
from app.schemas.enums import enum_field


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class GoalCreateRequest(BaseModel):
    """목표 생성 요청."""

    type: GoalType = enum_field(GoalType)
    title: str = Field(..., min_length=1, max_length=200)
    target_amount: int = Field(..., gt=0)
    start_date: date
    end_date: date
    family_group_id: UUID | None = None


class GoalUpdateRequest(BaseModel):
    """목표 수정 요청 (부분 업데이트)."""

    title: str | None = Field(None, min_length=1, max_length=200)
    target_amount: int | None = Field(None, gt=0)
    current_amount: int | None = Field(None, ge=0)
    start_date: date | None = None
    end_date: date | None = None


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class GoalResponse(UTCDatetimeResponse):
    """목표 응답."""

    id: UUID
    user_id: UUID
    family_group_id: UUID | None
    type: str
    title: str
    target_amount: int
    current_amount: int
    start_date: date
    end_date: date
    status: str
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class GoalDetailResponse(GoalResponse):
    """목표 상세 응답 (진행률 포함)."""

    progress_rate: float
