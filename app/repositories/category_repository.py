"""
CategoryConfig CRUD 레포지토리.

CategoryConfig 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
소유자(사용자/가족 그룹) 기반 접근 제어 쿼리를 지원한다.
"""

import logging
from uuid import UUID

from sqlalchemy import delete as sa_delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category_config import CategoryConfig

logger = logging.getLogger(__name__)


class CategoryRepository:
    """CategoryConfig 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────

    async def create(self, data: dict) -> CategoryConfig:
        """카테고리를 생성하고 반환한다."""
        category = CategoryConfig(**data)
        self._session.add(category)
        await self._session.flush()
        await self._session.refresh(category)
        logger.info("카테고리 생성 완료: category_id=%s", category.id)
        return category

    async def get_by_id(self, category_id: UUID) -> CategoryConfig | None:
        """UUID로 카테고리를 조회한다."""
        stmt = select(CategoryConfig).where(CategoryConfig.id == category_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list(
        self,
        owner_id: UUID,
        owner_type: str,
        area: str | None = None,
        type: str | None = None,
    ) -> list[CategoryConfig]:
        """소유자의 카테고리 목록을 필터링하여 sort_order 순으로 반환한다.

        Args:
            owner_id: 소유자 ID (사용자 또는 가족 그룹)
            owner_type: 소유자 유형 (USER, FAMILY_GROUP)
            area: 거래 영역 필터 (선택)
            type: 거래 유형 필터 (선택)

        Returns:
            sort_order 오름차순으로 정렬된 카테고리 목록
        """
        # 소유자 기반 접근 제어
        conditions = [
            CategoryConfig.owner_id == owner_id,
            CategoryConfig.owner_type == owner_type,
        ]

        # 선택적 필터 적용
        if area is not None:
            conditions.append(CategoryConfig.area == area)
        if type is not None:
            conditions.append(CategoryConfig.type == type)

        stmt = (
            select(CategoryConfig)
            .where(*conditions)
            .order_by(CategoryConfig.sort_order.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, category_id: UUID, data: dict) -> CategoryConfig:
        """카테고리 정보를 갱신하고 반환한다."""
        stmt = (
            update(CategoryConfig)
            .where(CategoryConfig.id == category_id)
            .values(**data)
            .returning(CategoryConfig)
        )
        result = await self._session.execute(stmt)
        category = result.scalar_one()
        await self._session.flush()
        logger.info("카테고리 갱신 완료: category_id=%s", category_id)
        return category

    async def delete(self, category_id: UUID) -> None:
        """카테고리를 삭제한다."""
        stmt = sa_delete(CategoryConfig).where(CategoryConfig.id == category_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("카테고리 삭제 완료: category_id=%s", category_id)

    # ──────────────────────────────────────────────
    # 정렬 순서 일괄 변경
    # ──────────────────────────────────────────────

    async def bulk_update_sort_order(self, items: list[dict]) -> None:
        """카테고리 정렬 순서를 일괄 변경한다.

        Args:
            items: 정렬 순서 변경 목록. 각 항목은 {"id": UUID, "sort_order": int} 형태.
        """
        for item in items:
            stmt = (
                update(CategoryConfig)
                .where(CategoryConfig.id == item["id"])
                .values(sort_order=item["sort_order"])
            )
            await self._session.execute(stmt)
        await self._session.flush()
        logger.info("카테고리 정렬 순서 일괄 변경 완료: %d건", len(items))

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    async def get_max_sort_order(
        self,
        owner_id: UUID,
        owner_type: str,
        area: str,
        type: str,
    ) -> int:
        """주어진 소유자/영역/유형 조합의 최대 sort_order를 반환한다.

        새 카테고리 생성 시 다음 sort_order를 할당하기 위해 사용한다.

        Args:
            owner_id: 소유자 ID
            owner_type: 소유자 유형
            area: 거래 영역
            type: 거래 유형

        Returns:
            현재 최대 sort_order 값. 카테고리가 없으면 0을 반환한다.
        """
        stmt = (
            select(func.coalesce(func.max(CategoryConfig.sort_order), 0))
            .where(
                CategoryConfig.owner_id == owner_id,
                CategoryConfig.owner_type == owner_type,
                CategoryConfig.area == area,
                CategoryConfig.type == type,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
