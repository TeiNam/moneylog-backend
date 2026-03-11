"""
예산(Budget) CRUD 레포지토리.

Budget 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from uuid import UUID

from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget

logger = logging.getLogger(__name__)


class BudgetRepository:
    """예산 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: dict) -> Budget:
        """예산을 생성하고 반환한다."""
        budget = Budget(**data)
        self._session.add(budget)
        await self._session.flush()
        await self._session.refresh(budget)
        logger.info("예산 생성 완료: budget_id=%s", budget.id)
        return budget

    async def get_by_id(self, budget_id: UUID) -> Budget | None:
        """UUID로 예산을 조회한다."""
        stmt = select(Budget).where(Budget.id == budget_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_user_month(
        self, user_id: UUID, year: int, month: int
    ) -> list[Budget]:
        """사용자의 특정 연월 예산 목록을 반환한다."""
        stmt = select(Budget).where(
            Budget.user_id == user_id,
            Budget.year == year,
            Budget.month == month,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, budget_id: UUID, data: dict) -> Budget:
        """예산 정보를 갱신하고 반환한다."""
        stmt = (
            update(Budget)
            .where(Budget.id == budget_id)
            .values(**data)
            .returning(Budget)
        )
        result = await self._session.execute(stmt)
        budget = result.scalar_one()
        await self._session.flush()
        logger.info("예산 갱신 완료: budget_id=%s", budget_id)
        return budget

    async def delete(self, budget_id: UUID) -> None:
        """예산을 삭제한다."""
        stmt = sa_delete(Budget).where(Budget.id == budget_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("예산 삭제 완료: budget_id=%s", budget_id)
