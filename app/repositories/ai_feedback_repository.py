"""
AIFeedback CRUD 레포지토리.

AIFeedback 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_feedback import AIFeedback

logger = logging.getLogger(__name__)


class AIFeedbackRepository:
    """AI 피드백 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: dict) -> AIFeedback:
        """피드백 레코드를 생성하고 반환한다."""
        feedback = AIFeedback(**data)
        self._session.add(feedback)
        await self._session.flush()
        await self._session.refresh(feedback)
        logger.info("AI 피드백 생성 완료: feedback_id=%s", feedback.id)
        return feedback

    async def get_list_by_user(
        self,
        user_id: UUID,
        feedback_type: str | None = None,
        transaction_id: int | None = None,
    ) -> list[AIFeedback]:
        """사용자의 피드백 이력을 최신순(created_at DESC)으로 반환한다."""
        conditions = [AIFeedback.user_id == user_id]

        if feedback_type is not None:
            conditions.append(AIFeedback.feedback_type == feedback_type)
        if transaction_id is not None:
            conditions.append(AIFeedback.transaction_id == transaction_id)

        stmt = (
            select(AIFeedback)
            .where(*conditions)
            .order_by(AIFeedback.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_by_user(
        self, user_id: UUID, limit: int = 20
    ) -> list[AIFeedback]:
        """사용자의 최근 피드백을 최신순으로 반환한다 (프롬프트 강화용)."""
        stmt = (
            select(AIFeedback)
            .where(AIFeedback.user_id == user_id)
            .order_by(AIFeedback.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
