"""
ChatMessage CRUD 레포지토리.

ChatMessage 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.

월별 RANGE 파티셔닝이 적용된 테이블이므로, 목록 조회 시
created_at 범위 조건을 포함하여 파티션 프루닝(partition pruning)이
동작하도록 한다.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage

logger = logging.getLogger(__name__)


class ChatMessageRepository:
    """AI 채팅 메시지 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: dict) -> ChatMessage:
        """메시지 레코드를 생성하고 반환한다."""
        message = ChatMessage(**data)
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        logger.info("채팅 메시지 생성 완료: message_id=%s", message.id)
        return message

    async def get_by_id(self, message_id: UUID) -> ChatMessage | None:
        """UUID로 메시지를 조회한다."""
        stmt = select(ChatMessage).where(ChatMessage.id == message_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_public_id(self, public_id: UUID) -> ChatMessage | None:
        """외부 API용 UUID(public_id)로 채팅 메시지를 조회한다."""
        stmt = select(ChatMessage).where(ChatMessage.public_id == public_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_session(
        self,
        session_id: UUID,
        *,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> list[ChatMessage]:
        """세션의 메시지 목록을 시간순(created_at ASC)으로 반환한다.

        파티션 프루닝(partition pruning)을 위해 created_at 범위 조건을
        지정할 수 있다. 범위가 지정되면 해당 파티션만 스캔한다.

        Args:
            session_id: 세션 UUID
            created_after: 이 시각 이후의 메시지만 조회 (inclusive)
            created_before: 이 시각 이전의 메시지만 조회 (exclusive)
        """
        conditions = [ChatMessage.session_id == session_id]
        # 파티션 프루닝을 위한 created_at 범위 조건
        if created_after is not None:
            conditions.append(ChatMessage.created_at >= created_after)
        if created_before is not None:
            conditions.append(ChatMessage.created_at < created_before)

        stmt = (
            select(ChatMessage)
            .where(*conditions)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_by_session(
        self,
        session_id: UUID,
        limit: int = 20,
        *,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> list[ChatMessage]:
        """세션의 최근 메시지를 시간순으로 반환한다 (컨텍스트용).

        created_at DESC로 limit개를 가져온 뒤 역순으로 정렬하여
        시간순(오래된 것 → 최신)으로 반환한다.

        파티션 프루닝(partition pruning)을 위해 created_at 범위 조건을
        지정할 수 있다.

        Args:
            session_id: 세션 UUID
            limit: 최대 반환 메시지 수
            created_after: 이 시각 이후의 메시지만 조회 (inclusive)
            created_before: 이 시각 이전의 메시지만 조회 (exclusive)
        """
        conditions = [ChatMessage.session_id == session_id]
        # 파티션 프루닝을 위한 created_at 범위 조건
        if created_after is not None:
            conditions.append(ChatMessage.created_at >= created_after)
        if created_before is not None:
            conditions.append(ChatMessage.created_at < created_before)

        stmt = (
            select(ChatMessage)
            .where(*conditions)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        messages = list(result.scalars().all())
        # 시간순으로 역정렬
        messages.reverse()
        return messages

    async def delete_by_session(
        self,
        session_id: UUID,
        *,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> None:
        """세션의 모든 메시지를 삭제한다.

        파티션 프루닝(partition pruning)을 위해 created_at 범위 조건을
        지정할 수 있다.

        Args:
            session_id: 세션 UUID
            created_after: 이 시각 이후의 메시지만 삭제 (inclusive)
            created_before: 이 시각 이전의 메시지만 삭제 (exclusive)
        """
        conditions = [ChatMessage.session_id == session_id]
        # 파티션 프루닝을 위한 created_at 범위 조건
        if created_after is not None:
            conditions.append(ChatMessage.created_at >= created_after)
        if created_before is not None:
            conditions.append(ChatMessage.created_at < created_before)

        stmt = sa_delete(ChatMessage).where(*conditions)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("세션 메시지 일괄 삭제 완료: session_id=%s", session_id)

    async def update(self, message_id: UUID, data: dict) -> ChatMessage:
        """메시지 레코드를 갱신한다 (extracted_data 등)."""
        stmt = (
            update(ChatMessage)
            .where(ChatMessage.id == message_id)
            .values(**data)
            .returning(ChatMessage)
        )
        result = await self._session.execute(stmt)
        message = result.scalar_one()
        await self._session.flush()
        logger.info("채팅 메시지 갱신 완료: message_id=%s", message_id)
        return message
