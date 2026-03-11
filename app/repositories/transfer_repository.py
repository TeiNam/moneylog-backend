"""
Transfer CRUD 레포지토리.

Transfer 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
사용자 기반 이체 내역 조회 및 날짜 필터링을 지원한다.
"""

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import Row, delete as sa_delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transfer import Transfer
from app.schemas.transfer import TransferCreateData

logger = logging.getLogger(__name__)


class TransferRepository:
    """이체 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────

    async def create(self, data: TransferCreateData) -> Transfer:
        """이체 레코드를 생성하고 반환한다."""
        # Pydantic 모델을 dict로 변환하여 SQLAlchemy 모델 생성
        transfer = Transfer(**data.model_dump())
        self._session.add(transfer)
        await self._session.flush()
        await self._session.refresh(transfer)
        logger.info("이체 생성 완료: transfer_id=%s", transfer.id)
        return transfer

    async def get_by_id(self, transfer_id: UUID) -> Transfer | None:
        """UUID로 이체를 조회한다."""
        stmt = select(Transfer).where(Transfer.id == transfer_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list_by_user(
        self,
        user_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Row]:
        """사용자의 이체 내역을 최신순(transfer_date DESC)으로 반환한다.

        필요 컬럼만 명시적으로 조회하여 불필요한 데이터 전송을 줄인다.

        Args:
            user_id: 현재 사용자 ID
            start_date: 시작일 필터 (선택, 이상)
            end_date: 종료일 필터 (선택, 이하)

        Returns:
            transfer_date 내림차순으로 정렬된 이체 Row 목록. Row 객체는 속성 접근(row.id 등)을 지원한다.
        """
        # 기본 조건: 사용자 ID 일치
        conditions = [Transfer.user_id == user_id]

        # 날짜 필터 적용
        if start_date is not None:
            conditions.append(Transfer.transfer_date >= start_date)
        if end_date is not None:
            conditions.append(Transfer.transfer_date <= end_date)

        # 이체 목록 API 응답에 필요한 컬럼만 명시 조회 (SELECT * 제거)
        stmt = (
            select(
                Transfer.id,
                Transfer.user_id,
                Transfer.family_group_id,
                Transfer.from_asset_id,
                Transfer.to_asset_id,
                Transfer.amount,
                Transfer.fee,
                Transfer.description,
                Transfer.transfer_date,
                Transfer.created_at,
                Transfer.updated_at,
            )
            .where(*conditions)
            .order_by(Transfer.transfer_date.desc())
        )
        result = await self._session.execute(stmt)
        # 컬럼 명시 조회 시 Row 객체 반환 (scalars() 대신 all() 사용)
        return list(result.all())

    async def update(self, transfer_id: UUID, data: dict) -> Transfer:
        """이체 레코드를 갱신하고 반환한다."""
        stmt = (
            update(Transfer)
            .where(Transfer.id == transfer_id)
            .values(**data)
            .returning(Transfer)
        )
        result = await self._session.execute(stmt)
        transfer = result.scalar_one()
        await self._session.flush()
        logger.info("이체 갱신 완료: transfer_id=%s", transfer_id)
        return transfer

    async def delete(self, transfer_id: UUID) -> None:
        """이체 레코드를 삭제한다."""
        stmt = sa_delete(Transfer).where(Transfer.id == transfer_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("이체 삭제 완료: transfer_id=%s", transfer_id)

