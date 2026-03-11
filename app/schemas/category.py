"""
카테고리(Category) 관련 Pydantic 요청/응답 스키마.

카테고리 생성, 수정, 조회, 정렬 순서 변경 등
카테고리 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Area, TransactionType


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class CategoryCreateRequest(BaseModel):
    """카테고리 생성 요청 스키마."""

    area: Area
    type: TransactionType
    major_category: str = Field(..., min_length=1, description="대분류 카테고리 이름")
    minor_categories: list[str] = Field(default=[], description="소분류 카테고리 목록")
    icon: str | None = None
    color: str | None = Field(
        default=None, max_length=7, description="색상 코드 (#RRGGBB)"
    )


class CategoryUpdateRequest(BaseModel):
    """카테고리 수정 요청 스키마 (부분 업데이트)."""

    major_category: str | None = None
    minor_categories: list[str] | None = None
    icon: str | None = None
    color: str | None = Field(
        default=None, max_length=7, description="색상 코드 (#RRGGBB)"
    )
    is_active: bool | None = None


class SortOrderItem(BaseModel):
    """정렬 순서 변경 항목."""

    id: UUID
    sort_order: int


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class CategoryResponse(BaseModel):
    """카테고리 응답 스키마."""

    id: UUID
    owner_id: UUID
    owner_type: str
    area: str
    type: str
    major_category: str
    minor_categories: list[str]
    icon: str | None
    color: str | None
    is_active: bool
    is_default: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
