"""
예산(Budget) 관련 HTTP 엔드포인트.

예산 생성, 목록 조회, 수정, 삭제, 예산 대비 실적 조회를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.budget_repository import BudgetRepository
from app.repositories.stats_repository import StatsRepository
from app.schemas.budget import (
    BudgetCreateRequest,
    BudgetPerformanceResponse,
    BudgetResponse,
    BudgetUpdateRequest,
)
from app.services.budget_service import BudgetService

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _build_service(db: AsyncSession) -> BudgetService:
    """DB 세션으로 BudgetService 인스턴스를 생성한다."""
    return BudgetService(
        BudgetRepository(db),
        stats_repo=StatsRepository(db),
    )


# ──────────────────────────────────────────────
# 예산 생성
# ──────────────────────────────────────────────


@router.post(
    "/",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="예산 생성",
)
async def create_budget(
    body: BudgetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BudgetResponse:
    """새로운 예산을 생성한다."""
    service = _build_service(db)
    budget = await service.create(current_user, body)
    await db.commit()
    return BudgetResponse.model_validate(budget)


# ──────────────────────────────────────────────
# 예산 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[BudgetResponse],
    summary="예산 목록 조회",
)
async def list_budgets(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BudgetResponse]:
    """해당 연월의 예산 목록을 조회한다."""
    service = _build_service(db)
    budgets = await service.get_list(current_user, year, month)
    return [BudgetResponse.model_validate(b) for b in budgets]


# ──────────────────────────────────────────────
# 예산 대비 실적 조회 (/{budget_id} 경로보다 먼저 정의)
# ──────────────────────────────────────────────


@router.get(
    "/performance",
    response_model=list[BudgetPerformanceResponse],
    summary="예산 대비 실적 조회",
)
async def get_budget_performance(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BudgetPerformanceResponse]:
    """예산 대비 실적을 조회한다."""
    service = _build_service(db)
    return await service.get_performance(current_user, year, month)


# ──────────────────────────────────────────────
# 예산 수정
# ──────────────────────────────────────────────


@router.put(
    "/{budget_id}",
    response_model=BudgetResponse,
    summary="예산 수정",
)
async def update_budget(
    budget_id: UUID,
    body: BudgetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BudgetResponse:
    """예산 정보를 수정한다."""
    service = _build_service(db)
    budget = await service.update(current_user, budget_id, body)
    await db.commit()
    return BudgetResponse.model_validate(budget)


# ──────────────────────────────────────────────
# 예산 삭제
# ──────────────────────────────────────────────


@router.delete(
    "/{budget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="예산 삭제",
)
async def delete_budget(
    budget_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """예산을 삭제한다."""
    service = _build_service(db)
    await service.delete(current_user, budget_id)
    await db.commit()
