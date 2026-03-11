"""
AI 피드백(Feedback) 관련 HTTP 엔드포인트.

피드백 제출, 피드백 이력 조회를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.ai_feedback_repository import AIFeedbackRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.ai_feedback import (
    FeedbackCreateRequest,
    FeedbackDetailResponse,
    FeedbackResponse,
)
from app.services.ai_feedback_service import AIFeedbackService

router = APIRouter(prefix="/ai/feedbacks", tags=["ai-feedbacks"])


def _build_service(db: AsyncSession) -> AIFeedbackService:
    """DB 세션으로 AIFeedbackService 인스턴스를 생성한다."""
    return AIFeedbackService(
        feedback_repo=AIFeedbackRepository(db),
        transaction_repo=TransactionRepository(db),
    )


# ──────────────────────────────────────────────
# 피드백 제출
# ──────────────────────────────────────────────


@router.post(
    "/",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="피드백 제출",
)
async def create_feedback(
    body: FeedbackCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """AI 오분류에 대한 피드백을 제출한다."""
    service = _build_service(db)
    feedback = await service.create_feedback(current_user, body)
    await db.commit()
    return FeedbackResponse.model_validate(feedback)


# ──────────────────────────────────────────────
# 피드백 이력 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[FeedbackDetailResponse],
    summary="피드백 이력 조회",
)
async def list_feedbacks(
    feedback_type: str | None = Query(None, description="피드백 유형 필터"),
    transaction_id: int | None = Query(None, description="거래 ID 필터"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedbackDetailResponse]:
    """현재 사용자의 피드백 이력을 조회한다."""
    service = _build_service(db)
    feedbacks = await service.get_feedbacks(
        current_user,
        feedback_type=feedback_type,
        transaction_id=transaction_id,
    )
    return [FeedbackDetailResponse(**fb) for fb in feedbacks]
