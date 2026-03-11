"""
ReceiptScan CRUD 레포지토리.

ReceiptScan 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt_scan import ReceiptScan

logger = logging.getLogger(__name__)


class ReceiptScanRepository:
    """영수증 스캔 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: dict) -> ReceiptScan:
        """스캔 레코드를 생성하고 반환한다."""
        scan = ReceiptScan(**data)
        self._session.add(scan)
        await self._session.flush()
        await self._session.refresh(scan)
        logger.info("영수증 스캔 생성 완료: scan_id=%s", scan.id)
        return scan

    async def get_by_id(self, scan_id: UUID) -> ReceiptScan | None:
        """UUID로 스캔을 조회한다."""
        stmt = select(ReceiptScan).where(ReceiptScan.id == scan_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_user(
        self, user_id: UUID, status: str | None = None
    ) -> list[ReceiptScan]:
        """사용자의 스캔 이력을 최신순(created_at DESC)으로 반환한다.

        status가 제공되면 해당 상태만 필터링한다.
        """
        conditions = [ReceiptScan.user_id == user_id]
        if status is not None:
            conditions.append(ReceiptScan.status == status)

        stmt = (
            select(ReceiptScan)
            .where(*conditions)
            .order_by(ReceiptScan.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, scan_id: UUID, data: dict) -> ReceiptScan:
        """스캔 레코드를 갱신한다 (status, raw_text, extracted_data, transaction_id 등)."""
        stmt = (
            update(ReceiptScan)
            .where(ReceiptScan.id == scan_id)
            .values(**data)
            .returning(ReceiptScan)
        )
        result = await self._session.execute(stmt)
        scan = result.scalar_one()
        await self._session.flush()
        logger.info("영수증 스캔 갱신 완료: scan_id=%s", scan_id)
        return scan
