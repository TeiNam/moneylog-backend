"""
이체(Transfer) 관련 Pydantic 요청/응답 스키마.

이체 생성, 조회 등
이체 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import date as Date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import UTCDatetimeResponse


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class TransferCreateRequest(BaseModel):
    """이체 생성 요청 스키마."""

    from_asset_id: UUID
    to_asset_id: UUID
    amount: int = Field(..., gt=0, description="이체 금액 (0보다 커야 함)")
    fee: int = Field(default=0, ge=0, description="이체 수수료 (기본값 0)")
    description: str | None = Field(None, max_length=200)
    transfer_date: Date

    @model_validator(mode="after")
    def validate_different_assets(self) -> "TransferCreateRequest":
        """출금 자산과 입금 자산이 동일하면 에러."""
        if self.from_asset_id == self.to_asset_id:
            raise ValueError("출금 자산과 입금 자산이 동일할 수 없습니다")
        return self


class TransferUpdateRequest(BaseModel):
    """이체 수정 요청 스키마 (부분 업데이트용)."""

    amount: int | None = Field(None, gt=0, description="이체 금액 (0보다 커야 함)")
    fee: int | None = Field(None, ge=0, description="이체 수수료 (0 이상)")
    description: str | None = Field(None, max_length=200, description="이체 설명 (200자 이내)")
    transfer_date: Date | None = Field(None, description="이체 날짜")


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class TransferResponse(UTCDatetimeResponse):
    """이체 응답 스키마."""

    id: UUID
    user_id: UUID
    family_group_id: UUID | None
    from_asset_id: UUID
    to_asset_id: UUID
    amount: int
    fee: int
    description: str | None
    transfer_date: Date
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TransferDetailResponse(TransferResponse):
    """이체 상세 응답 스키마 (자산명 포함)."""

    from_asset_name: str
    to_asset_name: str

# ──────────────────────────────────────────────
# 서비스 계층 반환 모델
# ──────────────────────────────────────────────


class TransferWithAssetNames(BaseModel):
    """서비스 계층 이체 상세 반환 모델.

    서비스 계층에서 이체 정보와 자산명을 함께 반환할 때 사용한다.
    기존 dict 반환 방식을 대체하여 타입 안전성을 확보한다.
    """

    transfer: TransferResponse
    from_asset_name: str
    to_asset_name: str

    model_config = ConfigDict(from_attributes=True)


# ──────────────────────────────────────────────
# 레포지토리 계층 생성 데이터 모델
# ──────────────────────────────────────────────


class TransferCreateData(BaseModel):
    """레포지토리 이체 생성 데이터 모델.

    레포지토리의 create 메서드에 dict 대신 전달하여
    타입 안전성과 런타임 유효성 검사를 확보한다.
    """

    user_id: UUID
    family_group_id: UUID | None = None
    from_asset_id: UUID
    to_asset_id: UUID
    amount: int = Field(gt=0, description="이체 금액 (0보다 커야 함)")
    fee: int = Field(default=0, ge=0, description="이체 수수료 (기본값 0)")
    description: str | None = None
    transfer_date: Date

