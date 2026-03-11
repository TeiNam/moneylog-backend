"""
Subscription CRUD 레포지토리.

Subscription 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from uuid import UUID

from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


class SubscriptionRepository:
    """구독 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────

    async def create(self, data: dict) -> Subscription:
        """구독을 생성하고 반환한다."""
        subscription = Subscription(**data)
        self._session.add(subscription)
        await self._session.flush()
        await self._session.refresh(subscription)
        logger.info("구독 생성 완료: subscription_id=%s", subscription.id)
        return subscription

    async def get_by_id(self, subscription_id: UUID) -> Subscription | None:
        """UUID로 구독을 조회한다."""
        stmt = select(Subscription).where(Subscription.id == subscription_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_user(
        self,
        user_id: UUID,
        status: str | None = None,
    ) -> list[Subscription]:
        """사용자의 구독 목록을 반환한다. status 필터 선택 적용.

        Args:
            user_id: 사용자 ID
            status: 구독 상태 필터 (None이면 전체 조회)

        Returns:
            구독 목록
        """
        conditions = [Subscription.user_id == user_id]
        if status is not None:
            conditions.append(Subscription.status == status)

        stmt = select(Subscription).where(*conditions)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, subscription_id: UUID, data: dict) -> Subscription:
        """구독 정보를 갱신하고 반환한다."""
        stmt = (
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(**data)
            .returning(Subscription)
        )
        result = await self._session.execute(stmt)
        subscription = result.scalar_one()
        await self._session.flush()
        logger.info("구독 갱신 완료: subscription_id=%s", subscription_id)
        return subscription

    async def delete(self, subscription_id: UUID) -> None:
        """구독을 삭제한다."""
        stmt = sa_delete(Subscription).where(Subscription.id == subscription_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("구독 삭제 완료: subscription_id=%s", subscription_id)

    # ──────────────────────────────────────────────
    # 배치 조회
    # ──────────────────────────────────────────────

    async def get_active_by_billing_day(self, billing_day: int) -> list[Subscription]:
        """특정 billing_day의 ACTIVE 구독을 조회한다.

        Args:
            billing_day: 결제일 (1~31)

        Returns:
            ACTIVE 상태이고 해당 billing_day인 구독 목록
        """
        stmt = select(Subscription).where(
            Subscription.status == "ACTIVE",
            Subscription.billing_day == billing_day,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_subscriptions(self) -> list[Subscription]:
        """모든 ACTIVE 구독을 조회한다."""
        stmt = select(Subscription).where(Subscription.status == "ACTIVE")
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user_and_status(self, user_id: UUID, status: str) -> int:
        """사용자의 특정 상태 구독 수를 반환한다."""
        from sqlalchemy import func

        stmt = select(func.count()).where(
            Subscription.user_id == user_id,
            Subscription.status == status,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

