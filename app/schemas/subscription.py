"""
구독(Subscription) 관련 Pydantic 요청/응답 스키마.

구독 생성, 수정, 조회, 요약, 배치 처리 등
구독 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import date as Date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    SubscriptionCategory,
    SubscriptionCycle,
    SubscriptionStatus,
)
from app.schemas.common import UTCDatetimeResponse
from app.schemas.enums import enum_field


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class SubscriptionCreateRequest(BaseModel):
    """구독 생성 요청 스키마."""

    service_name: str = Field(..., min_length=1, max_length=100)
    category: SubscriptionCategory = enum_field(SubscriptionCategory)
    amount: int = Field(..., gt=0)
    cycle: SubscriptionCycle = enum_field(SubscriptionCycle)
    billing_day: int = Field(..., ge=1, le=31)
    asset_id: UUID | None = None
    start_date: Date
    end_date: Date | None = None
    status: SubscriptionStatus = enum_field(
        SubscriptionStatus, default=SubscriptionStatus.ACTIVE
    )
    notify_before_days: int = Field(default=1, ge=0, le=30)
    memo: str | None = None


class SubscriptionUpdateRequest(BaseModel):
    """구독 수정 요청 스키마 (부분 업데이트)."""

    service_name: str | None = Field(None, min_length=1, max_length=100)
    category: SubscriptionCategory | None = enum_field(SubscriptionCategory, default=None)
    amount: int | None = Field(None, gt=0)
    cycle: SubscriptionCycle | None = enum_field(SubscriptionCycle, default=None)
    billing_day: int | None = Field(None, ge=1, le=31)
    asset_id: UUID | None = None
    start_date: Date | None = None
    end_date: Date | None = None
    status: SubscriptionStatus | None = enum_field(SubscriptionStatus, default=None)
    notify_before_days: int | None = Field(None, ge=0, le=30)
    memo: str | None = None


class BatchProcessRequest(BaseModel):
    """배치 처리 요청 스키마."""

    target_date: Date | None = None


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class SubscriptionResponse(UTCDatetimeResponse):
    """구독 응답 스키마."""

    id: UUID
    user_id: UUID
    family_group_id: UUID | None
    service_name: str
    category: str
    amount: int
    cycle: str
    billing_day: int
    asset_id: UUID | None
    start_date: Date
    end_date: Date | None
    status: str
    notify_before_days: int
    memo: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionDetailResponse(SubscriptionResponse):
    """구독 상세 응답 스키마 (다음 결제일 포함)."""

    next_billing_date: Date | None


class SubscriptionSummaryResponse(BaseModel):
    """구독 요약 응답 스키마."""

    monthly_total: int
    yearly_total: int
    active_count: int


class BatchProcessResult(BaseModel):
    """배치 처리 결과 스키마."""

    processed_count: int
    skipped_count: int
    target_date: Date


class BatchNotifyResult(BaseModel):
    """알림 배치 결과 스키마."""

    notified_count: int
    skipped_count: int
