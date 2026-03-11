"""
ChatSession CRUD 레포지토리.

ChatSession 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.

월별 RANGE 파티셔닝이 적용된 테이블이므로, 목록 조회 시
created_at 범위 조건을 포함하여 파티션 프루닝(partition pruning)이
동작하도록 한다.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession

logger = logging.getLogger(__name__)


class ChatSessionRepository:
    """AI 채팅 세션 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: dict) -> ChatSession:
        """세션 레코드를 생성하고 반환한다."""
        chat_session = ChatSession(**data)
        self._session.add(chat_session)
        await self._session.flush()
        await self._session.refresh(chat_session)
        logger.info("채팅 세션 생성 완료: session_id=%s", chat_session.id)
        return chat_session

    async def get_by_id(self, session_id: UUID) -> ChatSession | None:
        """UUID로 세션을 조회한다."""
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_user(
        self,
        user_id: UUID,
        *,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> list[ChatSession]:
        """사용자의 세션 목록을 최신순(created_at DESC)으로 반환한다.

        파티션 프루닝(partition pruning)을 위해 created_at 범위 조건을
        지정할 수 있다. 범위가 지정되면 해당 파티션만 스캔한다.

        Args:
            user_id: 사용자 UUID
            created_after: 이 시각 이후의 세션만 조회 (inclusive)
            created_before: 이 시각 이전의 세션만 조회 (exclusive)
        """
        conditions = [ChatSession.user_id == user_id]
        # 파티션 프루닝을 위한 created_at 범위 조건
        if created_after is not None:
            conditions.append(ChatSession.created_at >= created_after)
        if created_before is not None:
            conditions.append(ChatSession.created_at < created_before)

        stmt = (
            select(ChatSession)
            .where(*conditions)
            .order_by(ChatSession.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, session_id: UUID) -> None:
        """세션을 삭제한다."""
        stmt = sa_delete(ChatSession).where(ChatSession.id == session_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("채팅 세션 삭제 완료: session_id=%s", session_id)
