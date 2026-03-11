"""
AIFeedbackService — AI 오분류 피드백 수집 및 이력 관리 서비스.

피드백 생성 시 거래 존재/소유권/source 검증을 수행하고,
피드백 이력 조회 시 거래 기본 정보를 포함하여 반환한다.
"""

import logging
from uuid import UUID

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.ai_feedback import AIFeedback
from app.models.enums import TransactionSource
from app.repositories.ai_feedback_repository import AIFeedbackRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.ai_feedback import FeedbackCreateRequest

logger = logging.getLogger(__name__)


class AIFeedbackService:
    """AI 오분류 피드백 수집 및 이력 관리 서비스."""

    def __init__(
        self,
        feedback_repo: AIFeedbackRepository,
        transaction_repo: TransactionRepository,
    ) -> None:
        self._feedback_repo = feedback_repo
        self._transaction_repo = transaction_repo

    async def create_feedback(self, user, data: FeedbackCreateRequest) -> AIFeedback:
        """피드백을 생성한다.

        - 거래 존재 여부 검증
        - 거래 소유권 검증
        - 거래 source가 AI_CHAT 또는 RECEIPT_SCAN인지 검증
        - user_id는 현재 사용자로 자동 설정

        Raises:
            NotFoundError: 거래가 존재하지 않을 때
            ForbiddenError: 다른 사용자의 거래일 때
            BadRequestError: source가 MANUAL 또는 SUBSCRIPTION_AUTO일 때
        """
        # 거래 조회
        transaction = await self._transaction_repo.get_by_id(data.transaction_id)
        if transaction is None:
            raise NotFoundError("거래를 찾을 수 없습니다")

        # 소유권 검증
        if transaction.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

        # source 검증: AI 생성 거래에만 피드백 허용 (Enum 인스턴스 직접 비교)
        if transaction.source in (
            TransactionSource.MANUAL,
            TransactionSource.SUBSCRIPTION_AUTO,
        ):
            raise BadRequestError("AI 생성 거래에만 피드백을 제출할 수 있습니다")

        # 피드백 생성
        feedback = await self._feedback_repo.create({
            "user_id": user.id,
            "transaction_id": data.transaction_id,
            "feedback_type": data.feedback_type.value,
            "original_value": data.original_value,
            "corrected_value": data.corrected_value,
        })
        logger.info(
            "피드백 생성 완료: user_id=%s, transaction_id=%s, type=%s",
            user.id, data.transaction_id, data.feedback_type.value,
        )
        return feedback

    async def get_feedbacks(
        self,
        user,
        feedback_type: str | None = None,
        transaction_id: int | None = None,
    ) -> list[dict]:
        """피드백 이력을 조회한다. 각 피드백에 거래 기본 정보를 포함."""
        feedbacks = await self._feedback_repo.get_list_by_user(
            user.id, feedback_type, transaction_id,
        )

        result = []
        for fb in feedbacks:
            # 거래 기본 정보 조회
            tx = await self._transaction_repo.get_by_id(fb.transaction_id)
            tx_description = tx.description if tx else None
            tx_date = tx.date if tx else None

            result.append({
                "id": fb.id,
                "user_id": fb.user_id,
                "transaction_id": fb.transaction_id,
                "feedback_type": fb.feedback_type,
                "original_value": fb.original_value,
                "corrected_value": fb.corrected_value,
                "created_at": fb.created_at,
                "transaction_description": tx_description,
                "transaction_date": tx_date,
            })

        return result

    async def get_recent_feedbacks(
        self, user_id: UUID, limit: int = 20
    ) -> list[AIFeedback]:
        """프롬프트 강화용 최근 피드백을 조회한다."""
        return await self._feedback_repo.get_recent_by_user(user_id, limit)
