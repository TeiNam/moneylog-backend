"""
통계(Stats) 관련 HTTP 엔드포인트.

주간/월간/연간 통계 조회를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.budget_repository import BudgetRepository
from app.repositories.stats_repository import StatsRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.stats import (
    MonthlyStatsResponse,
    WeeklyStatsResponse,
    YearlyStatsResponse,
)
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


def _build_service(db: AsyncSession) -> StatsService:
    """DB 세션으로 StatsService 인스턴스를 생성한다."""
    return StatsService(
        StatsRepository(db),
        BudgetRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )


# ──────────────────────────────────────────────
# 주간 통계 조회
# ──────────────────────────────────────────────


@router.get(
    "/weekly",
    response_model=WeeklyStatsResponse,
    summary="주간 통계 조회",
)
async def get_weekly_stats(
    target_date: date = Query(..., alias="date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyStatsResponse:
    """해당 날짜가 속한 주의 통계를 조회한다."""
    service = _build_service(db)
    return await service.get_weekly_stats(current_user, target_date)


# ──────────────────────────────────────────────
# 월간 통계 조회
# ──────────────────────────────────────────────


@router.get(
    "/monthly",
    response_model=MonthlyStatsResponse,
    summary="월간 통계 조회",
)
async def get_monthly_stats(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonthlyStatsResponse:
    """해당 연월의 월간 통계를 조회한다."""
    service = _build_service(db)
    return await service.get_monthly_stats(current_user, year, month)


# ──────────────────────────────────────────────
# 연간 통계 조회
# ──────────────────────────────────────────────


@router.get(
    "/yearly",
    response_model=YearlyStatsResponse,
    summary="연간 통계 조회",
)
async def get_yearly_stats(
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> YearlyStatsResponse:
    """해당 연도의 연간 통계를 조회한다."""
    service = _build_service(db)
    return await service.get_yearly_stats(current_user, year)
