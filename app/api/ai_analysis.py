"""
AI 분석(Analysis) 관련 HTTP 엔드포인트.

월간 지출 분석 리포트, 절약 제안을 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.budget_repository import BudgetRepository
from app.repositories.stats_repository import StatsRepository
from app.schemas.ai_analysis import MonthlyAnalysisResponse, SavingsTipsResponse
from app.services.ai_analysis_service import AIAnalysisService
from app.services.bedrock_client import BedrockClient, BedrockError

router = APIRouter(prefix="/ai/analysis", tags=["ai-analysis"])


def _build_service(db: AsyncSession) -> AIAnalysisService:
    """DB 세션으로 AIAnalysisService 인스턴스를 생성한다."""
    return AIAnalysisService(
        stats_repo=StatsRepository(db),
        budget_repo=BudgetRepository(db),
        bedrock_client=BedrockClient(),
    )


# ──────────────────────────────────────────────
# 월간 지출 분석 리포트
# ──────────────────────────────────────────────


@router.get(
    "/monthly",
    response_model=MonthlyAnalysisResponse,
    summary="월간 지출 분석 리포트",
)
async def get_monthly_analysis(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonthlyAnalysisResponse | JSONResponse:
    """AI 기반 월간 지출 분석 리포트를 생성한다."""
    service = _build_service(db)
    try:
        return await service.get_monthly_analysis(
            current_user.id, year, month
        )
    except BedrockError as e:
        return JSONResponse(status_code=502, content={"detail": e.detail})


# ──────────────────────────────────────────────
# 절약 제안
# ──────────────────────────────────────────────


@router.get(
    "/savings-tips",
    response_model=SavingsTipsResponse,
    summary="절약 제안",
)
async def get_savings_tips(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavingsTipsResponse | JSONResponse:
    """예산 초과 카테고리에 대한 AI 절약 제안을 생성한다."""
    service = _build_service(db)
    try:
        return await service.get_savings_tips(
            current_user.id, year, month
        )
    except BedrockError as e:
        return JSONResponse(status_code=502, content={"detail": e.detail})
