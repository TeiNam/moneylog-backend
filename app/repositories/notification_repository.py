"""
Notification CRUD 레포지토리.

Notification 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationRepository:
    """알림 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────

    async def create(self, data: dict) -> Notification:
        """알림을 생성하고 반환한다."""
        notification = Notification(**data)
        self._session.add(notification)
        await self._session.flush()
        await self._session.refresh(notification)
        logger.info("알림 생성 완료: notification_id=%s", notification.id)
        return notification

    async def get_by_id(self, notification_id: UUID) -> Notification | None:
        """UUID로 알림을 조회한다."""
        stmt = select(Notification).where(Notification.id == notification_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_user(self, user_id: UUID) -> list[Notification]:
        """사용자의 알림 목록을 최신순(created_at 내림차순)으로 반환한다.

        Args:
            user_id: 사용자 ID

        Returns:
            최신순으로 정렬된 알림 목록
        """
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, notification_id: UUID, data: dict) -> Notification:
        """알림 정보를 갱신하고 반환한다."""
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id)
            .values(**data)
            .returning(Notification)
        )
        result = await self._session.execute(stmt)
        notification = result.scalar_one()
        await self._session.flush()
        logger.info("알림 갱신 완료: notification_id=%s", notification_id)
        return notification

    # ──────────────────────────────────────────────
    # 중복 확인
    # ──────────────────────────────────────────────

    async def exists_for_subscription_period(
        self,
        subscription_id: UUID,
        start_date: date,
        end_date: date,
    ) -> bool:
        """동일 구독 + 동일 결제 주기 내 알림 존재 여부를 확인한다.

        Args:
            subscription_id: 구독 ID
            start_date: 기간 시작일
            end_date: 기간 종료일

        Returns:
            해당 기간 내 알림이 존재하면 True
        """
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.subscription_id == subscription_id,
                Notification.created_at >= start_date,
                Notification.created_at <= end_date,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0
