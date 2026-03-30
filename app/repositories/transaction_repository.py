"""
Transaction CRUD 레포지토리.

Transaction, CarExpenseDetail, CeremonyEvent 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
사용자/가족 그룹 기반 접근 제어 쿼리를 지원한다.
"""

import logging
from datetime import date
from uuid import UUID

from sqlalchemy import Row, delete as sa_delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import CarExpenseDetail, CeremonyEvent, Transaction
from app.schemas.transaction import (
    CarDetailCreateData,
    CeremonyEventCreateData,
    TransactionCreateData,
)

logger = logging.getLogger(__name__)


class TransactionRepository:
    """Transaction, CarExpenseDetail, CeremonyEvent 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ──────────────────────────────────────────────
    # Transaction CRUD
    # ──────────────────────────────────────────────

    async def create(self, data: TransactionCreateData) -> Transaction:
        """거래를 생성하고 반환한다."""
        # Pydantic 모델을 dict로 변환하여 SQLAlchemy 모델 생성
        transaction = Transaction(**data.model_dump())
        self._session.add(transaction)
        await self._session.flush()
        await self._session.refresh(transaction)
        logger.info("거래 생성 완료: transaction_id=%s", transaction.id)
        return transaction

    async def get_by_id(self, transaction_id: int) -> Transaction | None:
        """내부 bigint PK로 거래를 조회한다."""
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_public_id(self, public_id: UUID) -> Transaction | None:
        """외부 API용 UUID(public_id)로 거래를 조회한다."""
        stmt = select(Transaction).where(Transaction.public_id == public_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


    async def get_list(
        self,
        user_id: UUID,
        family_group_id: UUID | None,
        filters: dict,
    ) -> tuple[list[Row], int]:
        """필터링 및 페이지네이션을 적용하여 거래 목록과 총 개수를 반환한다.

        Args:
            user_id: 현재 사용자 ID
            family_group_id: 가족 그룹 ID (가족 그룹 조회 시 사용)
            filters: 필터 조건 딕셔너리
                - family_group (bool): 가족 그룹 전체 조회 여부
                - start_date (date): 시작일
                - end_date (date): 종료일
                - area (str): 거래 영역
                - type (str): 거래 유형
                - major_category (str): 대분류 카테고리
                - asset_id (UUID): 자산 ID
                - offset (int): 페이지네이션 오프셋
                - limit (int): 페이지네이션 제한

        Returns:
            (거래 Row 목록, 총 개수) 튜플. Row 객체는 속성 접근(row.date 등)을 지원한다.
        """
        # 기본 쿼리: 사용자 또는 가족 그룹 기반 접근 제어
        use_family = filters.get("family_group", False)
        if use_family and family_group_id is not None:
            # 가족 그룹 전체 거래 조회
            # 다른 구성원의 비밀 거래(is_private=true)는 제외, 본인 거래는 모두 포함
            base_condition = Transaction.family_group_id == family_group_id
            # 본인 거래이거나 비밀이 아닌 거래만 포함
            private_filter = or_(
                Transaction.user_id == user_id,
                Transaction.is_private == False,  # noqa: E712
            )
        else:
            # 개인 거래만 조회 (본인 비밀 거래 포함)
            base_condition = Transaction.user_id == user_id
            private_filter = None

        # 필터 조건 구성
        conditions = [base_condition]
        if private_filter is not None:
            conditions.append(private_filter)

        if filters.get("start_date") is not None:
            conditions.append(Transaction.date >= filters["start_date"])
        if filters.get("end_date") is not None:
            conditions.append(Transaction.date <= filters["end_date"])
        if filters.get("area") is not None:
            conditions.append(Transaction.area == filters["area"])
        if filters.get("type") is not None:
            conditions.append(Transaction.type == filters["type"])
        if filters.get("major_category") is not None:
            conditions.append(
                Transaction.major_category == filters["major_category"]
            )
        if filters.get("asset_id") is not None:
            conditions.append(Transaction.asset_id == filters["asset_id"])

        # 총 개수 조회
        count_stmt = select(func.count()).select_from(Transaction).where(*conditions)
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        # 목록 조회: 필요 컬럼만 명시 (SELECT * 제거), 날짜 내림차순, 페이지네이션
        offset = filters.get("offset", 0)
        limit = filters.get("limit", 50)

        list_stmt = (
            select(
                Transaction.id,
                Transaction.public_id,
                Transaction.user_id,
                Transaction.family_group_id,
                Transaction.date,
                Transaction.area,
                Transaction.type,
                Transaction.major_category,
                Transaction.minor_category,
                Transaction.description,
                Transaction.amount,
                Transaction.discount,
                Transaction.actual_amount,
                Transaction.asset_id,
                Transaction.memo,
                Transaction.source,
                Transaction.is_private,
                Transaction.created_at,
                Transaction.updated_at,
            )
            .where(*conditions)
            .order_by(Transaction.date.desc())
            .offset(offset)
            .limit(limit)
        )
        list_result = await self._session.execute(list_stmt)
        # 컬럼 명시 조회 시 Row 객체 반환 (scalars() 대신 all() 사용)
        transactions = list(list_result.all())

        return transactions, total

    async def update(self, transaction_id: int, data: dict) -> Transaction:
        """거래 정보를 갱신하고 반환한다."""
        stmt = (
            update(Transaction)
            .where(Transaction.id == transaction_id)
            .values(**data)
            .returning(Transaction)
        )
        result = await self._session.execute(stmt)
        transaction = result.scalar_one()
        await self._session.flush()
        logger.info("거래 갱신 완료: transaction_id=%s", transaction_id)
        return transaction

    async def delete(self, transaction_id: int) -> None:
        """거래를 삭제한다."""
        stmt = sa_delete(Transaction).where(Transaction.id == transaction_id)
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("거래 삭제 완료: transaction_id=%s", transaction_id)

    # ──────────────────────────────────────────────
    # CarExpenseDetail CRUD
    # ──────────────────────────────────────────────

    async def create_car_detail(self, data: CarDetailCreateData) -> CarExpenseDetail:
        """차계부 상세를 생성하고 반환한다."""
        # Pydantic 모델을 dict로 변환하여 SQLAlchemy 모델 생성
        detail = CarExpenseDetail(**data.model_dump())
        self._session.add(detail)
        await self._session.flush()
        await self._session.refresh(detail)
        logger.info(
            "차계부 상세 생성 완료: transaction_id=%s", data.transaction_id
        )
        return detail

    async def get_car_detail_by_transaction_id(
        self, transaction_id: int
    ) -> CarExpenseDetail | None:
        """거래 ID로 차계부 상세를 조회한다."""
        stmt = select(CarExpenseDetail).where(
            CarExpenseDetail.transaction_id == transaction_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_car_detail(
        self, transaction_id: int, data: dict
    ) -> CarExpenseDetail:
        """거래 ID에 해당하는 차계부 상세를 갱신하고 반환한다."""
        stmt = (
            update(CarExpenseDetail)
            .where(CarExpenseDetail.transaction_id == transaction_id)
            .values(**data)
            .returning(CarExpenseDetail)
        )
        result = await self._session.execute(stmt)
        detail = result.scalar_one()
        await self._session.flush()
        logger.info("차계부 상세 갱신 완료: transaction_id=%s", transaction_id)
        return detail

    async def delete_car_detail_by_transaction_id(
        self, transaction_id: int
    ) -> None:
        """거래 ID에 해당하는 차계부 상세를 삭제한다."""
        stmt = sa_delete(CarExpenseDetail).where(
            CarExpenseDetail.transaction_id == transaction_id
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("차계부 상세 삭제 완료: transaction_id=%s", transaction_id)

    # ──────────────────────────────────────────────
    # CeremonyEvent CRUD
    # ──────────────────────────────────────────────

    async def create_ceremony_event(self, data: CeremonyEventCreateData) -> CeremonyEvent:
        """경조사 이벤트를 생성하고 반환한다."""
        # Pydantic 모델을 dict로 변환하여 SQLAlchemy 모델 생성
        event = CeremonyEvent(**data.model_dump())
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        logger.info(
            "경조사 이벤트 생성 완료: transaction_id=%s",
            data.transaction_id,
        )
        return event

    async def get_ceremony_event_by_transaction_id(
        self, transaction_id: int
    ) -> CeremonyEvent | None:
        """거래 ID로 경조사 이벤트를 조회한다."""
        stmt = select(CeremonyEvent).where(
            CeremonyEvent.transaction_id == transaction_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_ceremony_event(
        self, transaction_id: int, data: dict
    ) -> CeremonyEvent:
        """거래 ID에 해당하는 경조사 이벤트를 갱신하고 반환한다."""
        stmt = (
            update(CeremonyEvent)
            .where(CeremonyEvent.transaction_id == transaction_id)
            .values(**data)
            .returning(CeremonyEvent)
        )
        result = await self._session.execute(stmt)
        event = result.scalar_one()
        await self._session.flush()
        logger.info("경조사 이벤트 갱신 완료: transaction_id=%s", transaction_id)
        return event

    async def delete_ceremony_event_by_transaction_id(
        self, transaction_id: int
    ) -> None:
        """거래 ID에 해당하는 경조사 이벤트를 삭제한다."""
        stmt = sa_delete(CeremonyEvent).where(
            CeremonyEvent.transaction_id == transaction_id
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("경조사 이벤트 삭제 완료: transaction_id=%s", transaction_id)

    # ──────────────────────────────────────────────
    # Phase 4: 구독 자동 거래 중복 확인
    # ──────────────────────────────────────────────

    async def exists_subscription_auto(
        self,
        user_id: UUID,
        description: str,
        billing_date: date,
    ) -> bool:
        """동일 구독 + 동일 날짜에 SUBSCRIPTION_AUTO 거래가 존재하는지 확인한다.

        user_id + source + date + description 조합으로 중복을 판단한다.

        Args:
            user_id: 사용자 ID
            description: 구독 서비스 이름 (Transaction.description)
            billing_date: 결제일

        Returns:
            해당 조건의 거래가 존재하면 True
        """
        stmt = (
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.source == "SUBSCRIPTION_AUTO",
                Transaction.date == billing_date,
                Transaction.description == description,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    # ──────────────────────────────────────────────
    # Phase 6: 내보내기용 거래 목록 조회
    # ──────────────────────────────────────────────

    async def get_list_for_export(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        category: str | None = None,
        area: str | None = None,
    ) -> list[Row]:
        """내보내기용 거래 목록을 조회한다.

        현재 사용자의 거래만 포함하며, is_private=true도 포함한다 (본인 데이터).
        category, area 필터를 선택적으로 적용하고, date 오름차순으로 정렬한다.
        필요 컬럼만 명시적으로 조회하여 불필요한 데이터 전송을 줄인다.

        Args:
            user_id: 현재 사용자 ID
            start_date: 조회 시작일
            end_date: 조회 종료일
            category: 대분류 카테고리 필터 (선택)
            area: 영역 필터 (선택)

        Returns:
            date 오름차순으로 정렬된 거래 Row 목록. Row 객체는 속성 접근(row.date 등)을 지원한다.
        """
        # 기본 조건: 현재 사용자의 거래 + 날짜 범위
        conditions = [
            Transaction.user_id == user_id,
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        ]

        # 선택적 필터 적용
        if category is not None:
            conditions.append(Transaction.major_category == category)
        if area is not None:
            conditions.append(Transaction.area == area)

        # 내보내기에 필요한 컬럼만 명시 조회 (SELECT * 제거)
        stmt = (
            select(
                Transaction.id,
                Transaction.public_id,
                Transaction.date,
                Transaction.area,
                Transaction.type,
                Transaction.major_category,
                Transaction.minor_category,
                Transaction.description,
                Transaction.amount,
                Transaction.discount,
                Transaction.actual_amount,
                Transaction.asset_id,
                Transaction.memo,
                Transaction.is_private,
                Transaction.created_at,
            )
            .where(*conditions)
            .order_by(Transaction.date.asc())
        )
        result = await self._session.execute(stmt)
        # 컬럼 명시 조회 시 Row 객체 반환 (scalars() 대신 all() 사용)
        return list(result.all())

    # ──────────────────────────────────────────────
    # 집계
    # ──────────────────────────────────────────────

    async def sum_actual_amount(
        self,
        user_id: UUID,
        asset_id: UUID,
        start_date: date,
        end_date: date,
    ) -> int:
        """특정 자산의 기간 내 actual_amount 합계를 반환한다.

        거래가 없으면 0을 반환한다.

        Args:
            user_id: 사용자 ID
            asset_id: 자산 ID
            start_date: 시작일
            end_date: 종료일

        Returns:
            actual_amount 합계
        """
        stmt = select(
            func.coalesce(func.sum(Transaction.actual_amount), 0)
        ).where(
            Transaction.user_id == user_id,
            Transaction.asset_id == asset_id,
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()