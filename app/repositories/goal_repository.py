"""
목표(Goal) CRUD 레포지토리.

Goal 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from uuid import UUID

from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal

logger = logging.getLogger(__name__)


class GoalRepository:
    """목표 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: dict) -> Goal:
        """목표를 생성하고 반환한다."""
        goal = Goal(**data)
        self._session.add(goal)
        await self._session.flush()
        await self._session.refresh(goal)
        logger.info("목표 생성 완료: goal_id=%s", goal.id)
        return goal

    async def get_by_id(self, goal_id: UUID) -> Goal | None:
        """UUID로 목표를 조회한다."""
        stmt = select(Goal).where(Goal.id == goal_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_user(
        self, user_id: UUID, status: str | None = None
    ) -> list[Goal]:
        """사용자의 목표 목록을 반환한다. status 필터 선택 적용."""
        conditions = [Goal.user_id == user_id]
        if status is not None:
            conditions.append(Goal.status == status)
        stmt = select(Goal).where(*conditions)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, goal_id: UUID, data: dict) -> Goal:
        """목표 정보를 갱신하고 반환한다."""
        stmt = (
            update(Goal)
            .where(Goal.id == goal_id)
            .values(**data)
            .returning(Goal)
        )
        result = await self._session.execute(stmt)
        goal = result.scalar_one()
        await self._session.flush()
        logger.info("목표 갱신 완료: goal_id=%s", goal_id)
        return goal

    async def delete(self, goal_id: UUID) -> None:
        """목표를 삭제한다."""
        stmt = sa_delete(Goal).where(Goal.id == goal_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("목표 삭제 완료: goal_id=%s", goal_id)
