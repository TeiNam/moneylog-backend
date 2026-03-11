"""
FamilyGroup CRUD 레포지토리.

FamilyGroup 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from uuid import UUID

from sqlalchemy import delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_group import FamilyGroup

logger = logging.getLogger(__name__)


class FamilyGroupRepository:
    """FamilyGroup 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────

    async def create(self, data: dict) -> FamilyGroup:
        """가족 그룹을 생성하고 반환한다."""
        group = FamilyGroup(**data)
        self._session.add(group)
        await self._session.flush()
        await self._session.refresh(group)
        logger.info("가족 그룹 생성 완료: group_id=%s", group.id)
        return group

    async def get_by_id(self, group_id: UUID) -> FamilyGroup | None:
        """UUID로 가족 그룹을 조회한다."""
        stmt = select(FamilyGroup).where(FamilyGroup.id == group_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_invite_code(self, invite_code: str) -> FamilyGroup | None:
        """초대 코드로 가족 그룹을 조회한다."""
        stmt = select(FamilyGroup).where(FamilyGroup.invite_code == invite_code)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, group_id: UUID, data: dict) -> FamilyGroup:
        """가족 그룹 정보를 갱신하고 반환한다."""
        stmt = (
            update(FamilyGroup)
            .where(FamilyGroup.id == group_id)
            .values(**data)
            .returning(FamilyGroup)
        )
        result = await self._session.execute(stmt)
        group = result.scalar_one()
        await self._session.flush()
        logger.info("가족 그룹 갱신 완료: group_id=%s", group_id)
        return group

    async def delete(self, group_id: UUID) -> None:
        """가족 그룹을 삭제한다."""
        stmt = sa_delete(FamilyGroup).where(FamilyGroup.id == group_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("가족 그룹 삭제 완료: group_id=%s", group_id)
