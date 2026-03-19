"""
거래(Transaction) 관련 Pydantic 요청/응답 스키마.

거래 생성, 수정, 조회, 필터링 등
거래 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    Area,
    CarType,
    CeremonyDirection,
    CeremonyEventType,
    TransactionSource,
    TransactionType,
)
from app.schemas.common import UTCDatetimeResponse
from app.schemas.enums import enum_field


# ──────────────────────────────────────────────
# 상세 데이터 스키마
# ──────────────────────────────────────────────


class CarExpenseDetailSchema(BaseModel):
    """차계부 상세 데이터 스키마."""

    car_type: CarType = enum_field(CarType)
    fuel_amount_liter: Decimal | None = None
    fuel_unit_price: int | None = None
    odometer: int | None = None
    station_name: str | None = None


class CeremonyEventSchema(BaseModel):
    """경조사 이벤트 상세 데이터 스키마."""

    direction: CeremonyDirection = enum_field(CeremonyDirection)
    event_type: CeremonyEventType = enum_field(CeremonyEventType)
    person_name: str
    relationship: str
    venue: str | None = None


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class TransactionCreateRequest(BaseModel):
    """거래 생성 요청 스키마."""

    date: Date
    area: Area = enum_field(Area)
    type: TransactionType = enum_field(TransactionType)
    major_category: str
    minor_category: str = ""
    description: str = ""
    amount: int = Field(..., gt=0, description="결제 금액 (0보다 커야 함)")
    discount: int = 0
    asset_id: UUID | None = None
    memo: str | None = None
    source: TransactionSource = TransactionSource.MANUAL
    car_detail: CarExpenseDetailSchema | None = None
    ceremony_event: CeremonyEventSchema | None = None
    is_private: bool = False  # 비밀 거래 여부 (기본값 false)

    @model_validator(mode="after")
    def validate_area_detail(self) -> "TransactionCreateRequest":
        """영역별 상세 데이터 필수 검증.

        - area가 CAR이면 car_detail 필수
        - area가 EVENT이면 ceremony_event 필수
        """
        if self.area == Area.CAR and self.car_detail is None:
            raise ValueError("차계부(CAR) 영역 거래는 car_detail이 필수입니다")
        if self.area == Area.EVENT and self.ceremony_event is None:
            raise ValueError("경조사(EVENT) 영역 거래는 ceremony_event가 필수입니다")
        return self


class TransactionUpdateRequest(BaseModel):
    """거래 수정 요청 스키마 (부분 업데이트)."""

    date: Date | None = None
    area: Area | None = enum_field(Area, default=None)
    type: TransactionType | None = enum_field(TransactionType, default=None)
    major_category: str | None = None
    minor_category: str | None = None
    description: str | None = None
    amount: int | None = None
    discount: int | None = None
    asset_id: UUID | None = None
    memo: str | None = None
    car_detail: CarExpenseDetailSchema | None = None
    ceremony_event: CeremonyEventSchema | None = None
    is_private: bool | None = None  # 비밀 모드 변경


class TransactionFilterParams(BaseModel):
    """거래 목록 조회 필터 파라미터."""

    start_date: Date | None = None
    end_date: Date | None = None
    area: Area | None = enum_field(Area, default=None)
    type: TransactionType | None = enum_field(TransactionType, default=None)
    major_category: str | None = None
    asset_id: UUID | None = None
    family_group: bool = False
    offset: int = 0
    limit: int = Field(default=50, le=200)


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class TransactionResponse(UTCDatetimeResponse):
    """거래 응답 스키마."""

    id: int
    user_id: UUID
    family_group_id: UUID | None
    date: Date
    area: str
    type: str
    major_category: str
    minor_category: str
    description: str
    amount: int
    discount: int
    actual_amount: int
    asset_id: UUID | None
    memo: str | None
    source: str
    created_at: datetime
    updated_at: datetime | None
    is_private: bool  # 비밀 거래 여부

    model_config = ConfigDict(from_attributes=True)


class TransactionDetailResponse(TransactionResponse):
    """거래 상세 응답 스키마 (차계부/경조사 상세 포함)."""

    car_detail: CarExpenseDetailSchema | None = None
    ceremony_event: CeremonyEventSchema | None = None

# ──────────────────────────────────────────────
# 서비스 계층 반환 모델
# ──────────────────────────────────────────────


class TransactionDetailResult(BaseModel):
    """서비스 계층 거래 상세 반환 모델."""

    transaction: TransactionResponse
    car_detail: CarExpenseDetailSchema | None = None
    ceremony_event: CeremonyEventSchema | None = None

    model_config = ConfigDict(from_attributes=True)



# ──────────────────────────────────────────────
# 레포지토리 생성 데이터 모델
# ──────────────────────────────────────────────


class TransactionCreateData(BaseModel):
    """레포지토리 거래 생성 데이터 모델."""

    user_id: UUID
    family_group_id: UUID | None = None
    date: Date
    area: str
    type: str
    major_category: str
    minor_category: str = ""
    description: str = ""
    amount: int = Field(gt=0)
    discount: int = 0
    actual_amount: int
    asset_id: UUID | None = None
    memo: str | None = None
    source: str
    is_private: bool = False


class CarDetailCreateData(BaseModel):
    """레포지토리 차계부 상세 생성 데이터 모델."""

    transaction_id: int
    car_type: str
    fuel_amount_liter: Decimal | None = None
    fuel_unit_price: int | None = None
    odometer: int | None = None
    station_name: str | None = None


class CeremonyEventCreateData(BaseModel):
    """레포지토리 경조사 이벤트 생성 데이터 모델."""

    transaction_id: int
    direction: str
    event_type: str
    person_name: str
    relationship: str
    venue: str | None = None
