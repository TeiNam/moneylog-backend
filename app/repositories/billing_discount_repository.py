"""
BillingDiscount CRUD 레포지토리.

BillingDiscount 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import delete as sa_delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_discount import BillingDiscount

logger = logging.getLogger(__name__)


class BillingDiscountRepository:
    """BillingDiscount 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────

    async def create(self, data: dict) -> BillingDiscount:
        """청구할인을 생성하고 반환한다."""
        discount = BillingDiscount(**data)
        self._session.add(discount)
        await self._session.flush()
        await self._session.refresh(discount)
        logger.info("청구할인 생성 완료: discount_id=%s", discount.id)
        return discount

    async def get_by_id(self, discount_id: UUID) -> BillingDiscount | None:
        """UUID로 청구할인을 조회한다."""
        stmt = select(BillingDiscount).where(BillingDiscount.id == discount_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_asset_and_cycle(
        self,
        asset_id: UUID,
        cycle_start: date,
        cycle_end: date,
    ) -> list[BillingDiscount]:
        """자산 ID와 결제 주기로 청구할인 목록을 조회한다."""
        stmt = (
            select(BillingDiscount)
            .where(
                BillingDiscount.asset_id == asset_id,
                BillingDiscount.cycle_start == cycle_start,
                BillingDiscount.cycle_end == cycle_end,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, discount_id: UUID, data: dict) -> BillingDiscount:
        """청구할인 정보를 갱신하고 반환한다."""
        stmt = (
            update(BillingDiscount)
            .where(BillingDiscount.id == discount_id)
            .values(**data)
            .returning(BillingDiscount)
        )
        result = await self._session.execute(stmt)
        discount = result.scalar_one()
        await self._session.flush()
        logger.info("청구할인 갱신 완료: discount_id=%s", discount_id)
        return discount

    async def delete(self, discount_id: UUID) -> None:
        """청구할인을 삭제한다."""
        stmt = sa_delete(BillingDiscount).where(BillingDiscount.id == discount_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("청구할인 삭제 완료: discount_id=%s", discount_id)

    # ──────────────────────────────────────────────
    # 집계
    # ──────────────────────────────────────────────

    async def sum_by_asset_and_cycle(
        self,
        asset_id: UUID,
        cycle_start: date,
        cycle_end: date,
    ) -> int:
        """자산 ID와 결제 주기에 해당하는 청구할인 금액 합계를 반환한다.

        할인이 없으면 0을 반환한다.
        """
        stmt = select(
            func.coalesce(func.sum(BillingDiscount.amount), 0)
        ).where(
            BillingDiscount.asset_id == asset_id,
            BillingDiscount.cycle_start == cycle_start,
            BillingDiscount.cycle_end == cycle_end,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
