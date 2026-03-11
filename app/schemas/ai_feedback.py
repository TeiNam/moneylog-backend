"""AI 피드백 관련 Pydantic 스키마."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FeedbackType


class FeedbackCreateRequest(BaseModel):
    """피드백 생성 요청."""
    transaction_id: int
    feedback_type: FeedbackType
    original_value: str = Field(..., min_length=1, max_length=200)
    corrected_value: str = Field(..., min_length=1, max_length=200)


class FeedbackResponse(BaseModel):
    """피드백 응답."""
    id: UUID
    user_id: UUID
    transaction_id: int
    feedback_type: str
    original_value: str
    corrected_value: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FeedbackDetailResponse(FeedbackResponse):
    """피드백 상세 응답 (거래 기본 정보 포함)."""
    transaction_description: str | None = None
    transaction_date: date | None = None
