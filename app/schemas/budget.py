"""
예산(Budget) 관련 Pydantic 요청/응답 스키마.

예산 생성, 수정, 조회, 예산 대비 실적 등
예산 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class BudgetCreateRequest(BaseModel):
    """예산 생성 요청."""

    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    category: str = Field(..., min_length=1, max_length=50)
    budget_amount: int = Field(..., gt=0)
    family_group_id: UUID | None = None


class BudgetUpdateRequest(BaseModel):
    """예산 수정 요청 (부분 업데이트)."""

    category: str | None = Field(None, min_length=1, max_length=50)
    budget_amount: int | None = Field(None, gt=0)


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class BudgetResponse(BaseModel):
    """예산 응답."""

    id: UUID
    user_id: UUID
    family_group_id: UUID | None
    year: int
    month: int
    category: str
    budget_amount: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class BudgetPerformanceResponse(BaseModel):
    """예산 대비 실적 응답."""

    category: str
    budget_amount: int
    actual_amount: int
    remaining: int
    usage_rate: float
