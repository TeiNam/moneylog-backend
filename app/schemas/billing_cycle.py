"""
카드 결제 주기(Billing Cycle) 관련 Pydantic 요청/응답 스키마.

결제 주기 설정, 청구할인 CRUD, 결제 예정 금액 조회 등
결제 주기 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import date as Date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDatetimeResponse
from app.schemas.transaction import TransactionResponse


# ──────────────────────────────────────────────
# 결제 주기 스키마
# ──────────────────────────────────────────────


class BillingCycleResponse(BaseModel):
    """결제 주기 응답 스키마."""

    start_date: Date
    end_date: Date
    payment_date: Date


# ──────────────────────────────────────────────
# 결제 주기 설정 요청/응답 스키마
# ──────────────────────────────────────────────


class BillingConfigUpdateRequest(BaseModel):
    """결제 주기 설정 변경 요청 스키마."""

    payment_day: int = Field(..., ge=1, le=31, description="결제일 (1~31)")
    billing_start_day: int | None = Field(
        default=None, ge=1, le=31, description="사용 기준일 (1~31, 미입력 시 자동 역산)"
    )


class BillingConfigResponse(BaseModel):
    """결제 주기 설정 조회 응답 스키마."""

    asset_id: UUID
    payment_day: int | None
    billing_start_day: int | None
    current_cycle: BillingCycleResponse | None


# ──────────────────────────────────────────────
# 청구할인 요청/응답 스키마
# ──────────────────────────────────────────────


class BillingDiscountCreateRequest(BaseModel):
    """청구할인 등록 요청 스키마."""

    name: str = Field(..., min_length=1, max_length=100, description="할인명")
    amount: int = Field(..., ge=0, description="할인 금액 (0 이상)")
    cycle_start: Date = Field(..., description="적용 결제 주기 시작일")
    cycle_end: Date = Field(..., description="적용 결제 주기 종료일")
    memo: str | None = None


class BillingDiscountUpdateRequest(BaseModel):
    """청구할인 수정 요청 스키마 (부분 업데이트)."""

    name: str | None = None
    amount: int | None = Field(default=None, ge=0, description="할인 금액 (0 이상)")
    memo: str | None = None


class BillingDiscountResponse(UTCDatetimeResponse):
    """청구할인 응답 스키마."""

    id: UUID
    asset_id: UUID
    name: str
    amount: int
    cycle_start: Date
    cycle_end: Date
    memo: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────
# 결제 주기별 거래 및 요약 응답 스키마
# ──────────────────────────────────────────────


class BillingTransactionsResponse(BaseModel):
    """결제 주기별 거래 목록 응답 스키마."""

    cycle: BillingCycleResponse
    transactions: list[TransactionResponse]
    total_count: int


class BillingSummaryResponse(BaseModel):
    """결제 예정 금액 요약 응답 스키마."""

    cycle: BillingCycleResponse
    total_usage: int
    total_discount: int
    estimated_payment: int
    next_payment_date: Date
