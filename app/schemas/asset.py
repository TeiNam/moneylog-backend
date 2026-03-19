"""
자산(Asset) 관련 Pydantic 요청/응답 스키마.

자산 생성, 수정, 조회, 기본 자산 설정, 정렬 순서 변경 등
자산 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AssetType, Ownership
from app.schemas.common import UTCDatetimeResponse
from app.schemas.enums import enum_field


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class AssetCreateRequest(BaseModel):
    """자산 생성 요청 스키마."""

    name: str = Field(..., min_length=1, description="자산 이름")
    asset_type: AssetType = enum_field(AssetType, description="자산 유형")
    ownership: Ownership = enum_field(
        Ownership, default=Ownership.PERSONAL, description="소유권 구분"
    )
    family_group_id: UUID | None = None
    institution: str | None = Field(default=None, description="금융기관명")
    balance: int | None = Field(default=None, description="잔액")
    memo: str | None = Field(default=None, description="메모")
    icon: str | None = Field(default=None, description="아이콘")
    color: str | None = Field(
        default=None, max_length=7, description="색상 코드 (#RRGGBB)"
    )


class AssetUpdateRequest(BaseModel):
    """자산 수정 요청 스키마 (부분 업데이트)."""

    name: str | None = None
    asset_type: AssetType | None = enum_field(AssetType, default=None)
    institution: str | None = None
    balance: int | None = None
    memo: str | None = None
    icon: str | None = None
    color: str | None = Field(
        default=None, max_length=7, description="색상 코드 (#RRGGBB)"
    )
    is_active: bool | None = None


class DefaultAssetRequest(BaseModel):
    """기본 자산 설정 요청 스키마."""

    asset_id: UUID


class SortOrderItem(BaseModel):
    """정렬 순서 변경 항목."""

    asset_id: UUID
    sort_order: int


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class AssetResponse(UTCDatetimeResponse):
    """자산 응답 스키마."""

    id: UUID
    user_id: UUID
    family_group_id: UUID | None
    ownership: str
    name: str
    asset_type: str
    institution: str | None
    balance: int | None
    memo: str | None
    icon: str | None
    color: str | None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
