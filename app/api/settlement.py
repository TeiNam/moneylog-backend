"""
정산(Settlement) 관련 HTTP 엔드포인트.

가족 카드 사용 현황 조회 및 정산 계산을 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하며, 가족 그룹 소속 여부를 검증한다.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.stats_repository import StatsRepository
from app.repositories.user_repository import UserRepository
from app.schemas.settlement import FamilyUsageResponse, SettlementResponse
from app.services.settlement_service import SettlementService

router = APIRouter(prefix="/settlement", tags=["settlement"])


def _build_service(db: AsyncSession) -> SettlementService:
    """DB 세션으로 SettlementService 인스턴스를 생성한다."""
    return SettlementService(
        StatsRepository(db),
        UserRepository(db),
    )


# ──────────────────────────────────────────────
# 가족 카드 사용 현황 조회
# ──────────────────────────────────────────────


@router.get(
    "/usage",
    response_model=FamilyUsageResponse,
    summary="가족 카드 사용 현황 조회",
)
async def get_family_usage(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FamilyUsageResponse:
    """가족 그룹 내 구성원별 월간 지출 현황을 조회한다."""
    service = _build_service(db)
    return await service.get_family_usage(current_user, year, month)


# ──────────────────────────────────────────────
# 정산 계산
# ──────────────────────────────────────────────


@router.get(
    "/calculate",
    response_model=SettlementResponse,
    summary="정산 계산",
)
async def calculate_settlement(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    ratio: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettlementResponse:
    """가족 구성원 간 정산 결과를 계산한다."""
    service = _build_service(db)
    return await service.calculate_settlement(current_user, year, month, ratio=ratio)
