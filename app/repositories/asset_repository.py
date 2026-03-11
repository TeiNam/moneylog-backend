"""
Asset CRUD 레포지토리.

Asset 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
사용자/가족 그룹 기반 접근 제어 쿼리를 지원한다.
"""

import logging
from uuid import UUID

from sqlalchemy import delete as sa_delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset

logger = logging.getLogger(__name__)


class AssetRepository:
    """Asset 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────

    async def create(self, data: dict) -> Asset:
        """자산을 생성하고 반환한다."""
        asset = Asset(**data)
        self._session.add(asset)
        await self._session.flush()
        await self._session.refresh(asset)
        logger.info("자산 생성 완료: asset_id=%s", asset.id)
        return asset

    async def get_by_id(self, asset_id: UUID) -> Asset | None:
        """UUID로 자산을 조회한다."""
        stmt = select(Asset).where(Asset.id == asset_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ids(self, asset_ids: list[UUID]) -> list[Asset]:
        """여러 자산 ID를 받아 한 번의 쿼리로 자산 목록을 반환한다."""
        if not asset_ids:
            return []
        stmt = select(Asset).where(Asset.id.in_(asset_ids))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


    async def get_list_by_user(
        self,
        user_id: UUID,
        family_group_id: UUID | None = None,
    ) -> list[Asset]:
        """사용자의 개인 자산 + 가족 그룹 공유 자산을 sort_order 오름차순으로 반환한다.

        Args:
            user_id: 현재 사용자 ID (개인 자산 조회)
            family_group_id: 가족 그룹 ID (공유 자산 조회, None이면 개인 자산만)

        Returns:
            sort_order 오름차순으로 정렬된 자산 목록
        """
        # 개인 자산 조건
        conditions = [Asset.user_id == user_id]

        # 가족 그룹 공유 자산 조건 추가
        if family_group_id is not None:
            conditions.append(Asset.family_group_id == family_group_id)

        stmt = (
            select(Asset)
            .where(or_(*conditions))
            .order_by(Asset.sort_order.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, asset_id: UUID, data: dict) -> Asset:
        """자산 정보를 갱신하고 반환한다."""
        stmt = (
            update(Asset)
            .where(Asset.id == asset_id)
            .values(**data)
            .returning(Asset)
        )
        result = await self._session.execute(stmt)
        asset = result.scalar_one()
        await self._session.flush()
        logger.info("자산 갱신 완료: asset_id=%s", asset_id)
        return asset

    async def delete(self, asset_id: UUID) -> None:
        """자산을 삭제한다."""
        stmt = sa_delete(Asset).where(Asset.id == asset_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("자산 삭제 완료: asset_id=%s", asset_id)

    # ──────────────────────────────────────────────
    # 정렬 순서 갱신
    # ──────────────────────────────────────────────

    async def update_sort_order(self, asset_id: UUID, sort_order: int) -> None:
        """자산의 정렬 순서를 개별 갱신한다.

        Args:
            asset_id: 자산 ID
            sort_order: 새로운 정렬 순서
        """
        stmt = (
            update(Asset)
            .where(Asset.id == asset_id)
            .values(sort_order=sort_order)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("자산 정렬 순서 갱신 완료: asset_id=%s, sort_order=%d", asset_id, sort_order)
