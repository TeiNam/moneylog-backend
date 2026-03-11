"""
거래(Transaction) 비즈니스 로직 서비스.

거래 생성, 조회, 수정, 삭제를 담당하며,
area별 상세 데이터(차계부/경조사) 처리와 CeremonyPerson 누적 갱신을 포함한다.
권한 검증(본인 또는 같은 가족 그룹)을 수행한다.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import Area, CeremonyDirection
from sqlalchemy import Row

from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.ceremony_person_repository import CeremonyPersonRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import (
    CarDetailCreateData,
    CeremonyEventCreateData,
    TransactionCreateData,
    TransactionCreateRequest,
    TransactionDetailResult,
    TransactionFilterParams,
    TransactionUpdateRequest,
)

logger = logging.getLogger(__name__)


class TransactionService:
    """거래 CRUD 및 관련 상세 데이터 처리 서비스."""

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        ceremony_person_repo: CeremonyPersonRepository,
    ) -> None:
        self._repo = transaction_repo
        self._person_repo = ceremony_person_repo

    # ──────────────────────────────────────────────
    # 거래 생성
    # ──────────────────────────────────────────────

    async def create(
        self, user: User, data: TransactionCreateRequest
    ) -> Transaction:
        """거래를 생성하고, area별 상세 데이터 및 CeremonyPerson 누적을 처리한다.

        Args:
            user: 현재 인증된 사용자
            data: 거래 생성 요청 데이터

        Returns:
            생성된 Transaction 객체
        """
        # actual_amount 자동 계산
        actual_amount = data.amount - data.discount

        # Pydantic 모델로 거래 데이터 구성
        transaction_data = TransactionCreateData(
            user_id=user.id,
            family_group_id=user.family_group_id,
            date=data.date,
            area=data.area.value,
            type=data.type.value,
            major_category=data.major_category,
            minor_category=data.minor_category,
            description=data.description,
            amount=data.amount,
            discount=data.discount,
            actual_amount=actual_amount,
            asset_id=data.asset_id,
            memo=data.memo,
            source=data.source.value,
            is_private=data.is_private,
        )

        # 거래 레코드 생성
        transaction = await self._repo.create(transaction_data)

        # area별 상세 데이터 생성
        if data.area == Area.CAR and data.car_detail is not None:
            await self._create_car_detail(transaction.id, data.car_detail)

        if data.area == Area.EVENT and data.ceremony_event is not None:
            await self._create_ceremony_event_and_update_person(
                user, transaction.id, actual_amount, data.ceremony_event
            )

        logger.info(
            "거래 생성 완료: transaction_id=%s, area=%s",
            transaction.id,
            data.area.value,
        )
        return transaction

    # ──────────────────────────────────────────────
    # 거래 목록 조회
    # ──────────────────────────────────────────────

    async def get_list(
        self, user: User, filters: TransactionFilterParams
    ) -> tuple[list[Row], int]:
        """필터링 및 페이지네이션을 적용하여 거래 목록을 조회한다.

        Args:
            user: 현재 인증된 사용자
            filters: 필터 파라미터 (기간, area, type, major_category, asset_id 등)

        Returns:
            (거래 Row 목록, 총 개수) 튜플. Row 객체는 속성 접근(row.date 등)을 지원한다.
        """
        # 필터를 딕셔너리로 변환
        filters_dict = filters.model_dump(exclude_none=True)

        transactions, total = await self._repo.get_list(
            user_id=user.id,
            family_group_id=user.family_group_id,
            filters=filters_dict,
        )
        return transactions, total

    # ──────────────────────────────────────────────
    # 거래 상세 조회
    # ──────────────────────────────────────────────

    async def get_detail(self, user: User, transaction_id: int) -> "TransactionDetailResult":
        """거래와 관련 상세 데이터(차계부/경조사)를 함께 반환한다.

        Args:
            user: 현재 인증된 사용자
            transaction_id: 조회할 거래 ID

        Returns:
            거래 정보와 상세 데이터를 포함하는 TransactionDetailResult 모델

        Raises:
            NotFoundError: 거래가 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        transaction = await self._repo.get_by_id(transaction_id)
        if transaction is None:
            raise NotFoundError("거래를 찾을 수 없습니다")

        self._check_permission(user, transaction)

        # 다른 구성원의 비밀 거래 직접 조회 차단
        if transaction.user_id != user.id and transaction.is_private:
            raise ForbiddenError("해당 거래에 대한 접근 권한이 없습니다")

        # area별 상세 데이터 조회
        car_detail = None
        ceremony_event = None

        # Enum 인스턴스 직접 비교 (str, Enum 다중 상속으로 .value 불필요)
        if transaction.area == Area.CAR:
            car_detail = await self._repo.get_car_detail_by_transaction_id(
                transaction_id
            )

        if transaction.area == Area.EVENT:
            ceremony_event = (
                await self._repo.get_ceremony_event_by_transaction_id(
                    transaction_id
                )
            )

        # TransactionDetailResult Pydantic 모델로 반환
        return TransactionDetailResult(
            transaction=transaction,
            car_detail=car_detail,
            ceremony_event=ceremony_event,
        )

    # ──────────────────────────────────────────────
    # 거래 수정
    # ──────────────────────────────────────────────

    async def update(
        self,
        user: User,
        transaction_id: int,
        data: TransactionUpdateRequest,
    ) -> Transaction:
        """거래 및 관련 상세 레코드를 갱신한다.

        Args:
            user: 현재 인증된 사용자
            transaction_id: 수정할 거래 ID
            data: 거래 수정 요청 데이터

        Returns:
            갱신된 Transaction 객체

        Raises:
            NotFoundError: 거래가 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        transaction = await self._repo.get_by_id(transaction_id)
        if transaction is None:
            raise NotFoundError("거래를 찾을 수 없습니다")

        self._check_permission(user, transaction)

        # None이 아닌 필드만 업데이트 딕셔너리에 포함
        update_data: dict = {}
        for field in (
            "date",
            "area",
            "type",
            "major_category",
            "minor_category",
            "description",
            "amount",
            "discount",
            "asset_id",
            "memo",
            "is_private",
        ):
            value = getattr(data, field, None)
            if value is not None:
                # Enum 값은 문자열로 변환 (isinstance로 정확한 타입 판별)
                update_data[field] = (
                    value.value if isinstance(value, Enum) else value
                )

        # amount 또는 discount가 변경되면 actual_amount 재계산
        new_amount = update_data.get("amount", transaction.amount)
        new_discount = update_data.get("discount", transaction.discount)
        if "amount" in update_data or "discount" in update_data:
            update_data["actual_amount"] = new_amount - new_discount

        # updated_at 설정
        update_data["updated_at"] = datetime.now(timezone.utc)

        # 거래 레코드 갱신
        updated_transaction = await self._repo.update(
            transaction_id, update_data
        )

        # 차계부 상세 갱신
        if data.car_detail is not None:
            car_detail_data = data.car_detail.model_dump()
            # Enum 값 문자열 변환 (isinstance로 정확한 타입 판별)
            if "car_type" in car_detail_data and isinstance(
                car_detail_data["car_type"], Enum
            ):
                car_detail_data["car_type"] = car_detail_data[
                    "car_type"
                ].value

            existing = await self._repo.get_car_detail_by_transaction_id(
                transaction_id
            )
            if existing is not None:
                await self._repo.update_car_detail(
                    transaction_id, car_detail_data
                )
            else:
                # Pydantic 모델로 차계부 상세 데이터 구성
                create_data = CarDetailCreateData(
                    transaction_id=transaction_id,
                    **car_detail_data,
                )
                await self._repo.create_car_detail(create_data)

        # 경조사 이벤트 갱신
        if data.ceremony_event is not None:
            event_data = data.ceremony_event.model_dump()
            # Enum 값 문자열 변환 (isinstance로 정확한 타입 판별)
            for key in ("direction", "event_type"):
                if key in event_data and isinstance(event_data[key], Enum):
                    event_data[key] = event_data[key].value

            existing = (
                await self._repo.get_ceremony_event_by_transaction_id(
                    transaction_id
                )
            )
            if existing is not None:
                await self._repo.update_ceremony_event(
                    transaction_id, event_data
                )
            else:
                # Pydantic 모델로 경조사 이벤트 데이터 구성
                create_data = CeremonyEventCreateData(
                    transaction_id=transaction_id,
                    **event_data,
                )
                await self._repo.create_ceremony_event(create_data)

        logger.info("거래 수정 완료: transaction_id=%s", transaction_id)
        return updated_transaction

    # ──────────────────────────────────────────────
    # 거래 삭제
    # ──────────────────────────────────────────────

    async def delete(self, user: User, transaction_id: int) -> None:
        """거래 및 관련 상세 레코드를 삭제하고, CeremonyPerson 누적을 차감한다.

        Args:
            user: 현재 인증된 사용자
            transaction_id: 삭제할 거래 ID

        Raises:
            NotFoundError: 거래가 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        transaction = await self._repo.get_by_id(transaction_id)
        if transaction is None:
            raise NotFoundError("거래를 찾을 수 없습니다")

        self._check_permission(user, transaction)

        # area별 상세 레코드 삭제 (Enum 인스턴스 직접 비교)
        if transaction.area == Area.CAR:
            await self._repo.delete_car_detail_by_transaction_id(
                transaction_id
            )

        if transaction.area == Area.EVENT:
            # 경조사 이벤트 조회 후 CeremonyPerson 누적 차감
            ceremony_event = (
                await self._repo.get_ceremony_event_by_transaction_id(
                    transaction_id
                )
            )
            if ceremony_event is not None:
                await self._rollback_ceremony_person_totals(
                    user, transaction, ceremony_event
                )
                await self._repo.delete_ceremony_event_by_transaction_id(
                    transaction_id
                )

        # 거래 레코드 삭제
        await self._repo.delete(transaction_id)
        logger.info("거래 삭제 완료: transaction_id=%s", transaction_id)

    # ──────────────────────────────────────────────
    # 권한 검증
    # ──────────────────────────────────────────────

    def _check_permission(self, user: User, transaction: Transaction) -> None:
        """사용자가 해당 거래에 접근할 권한이 있는지 검증한다.

        본인이 작성한 거래이거나, 같은 가족 그룹에 속한 거래인 경우 허용한다.

        Raises:
            ForbiddenError: 접근 권한이 없을 때
        """
        # 본인 거래인 경우 허용
        if transaction.user_id == user.id:
            return

        # 같은 가족 그룹인 경우 허용
        if (
            user.family_group_id is not None
            and transaction.family_group_id == user.family_group_id
        ):
            return

        raise ForbiddenError("해당 거래에 대한 접근 권한이 없습니다")

    # ──────────────────────────────────────────────
    # 내부 헬퍼 메서드
    # ──────────────────────────────────────────────

    async def _create_car_detail(
        self, transaction_id: int, car_detail: "CarExpenseDetailSchema"
    ) -> None:
        """차계부 상세 레코드를 생성한다."""
        detail_data = car_detail.model_dump()
        # Enum 값 문자열 변환 (isinstance로 정확한 타입 판별)
        if "car_type" in detail_data and isinstance(
            detail_data["car_type"], Enum
        ):
            detail_data["car_type"] = detail_data["car_type"].value
        # Pydantic 모델로 차계부 상세 데이터 구성
        create_data = CarDetailCreateData(
            transaction_id=transaction_id,
            **detail_data,
        )
        await self._repo.create_car_detail(create_data)

    async def _create_ceremony_event_and_update_person(
        self,
        user: User,
        transaction_id: int,
        actual_amount: int,
        ceremony_event: "CeremonyEventSchema",
    ) -> None:
        """경조사 이벤트를 생성하고 CeremonyPerson 누적을 갱신한다."""
        event_data = ceremony_event.model_dump()
        # Enum 값 문자열 변환 (isinstance로 정확한 타입 판별)
        for key in ("direction", "event_type"):
            if key in event_data and isinstance(event_data[key], Enum):
                event_data[key] = event_data[key].value

        # Pydantic 모델로 경조사 이벤트 데이터 구성
        create_data = CeremonyEventCreateData(
            transaction_id=transaction_id,
            **event_data,
        )
        await self._repo.create_ceremony_event(create_data)

        # CeremonyPerson 조회 또는 생성 후 누적 갱신
        person = await self._person_repo.get_or_create(
            user_id=user.id,
            name=ceremony_event.person_name,
            relationship=ceremony_event.relationship,
        )

        if ceremony_event.direction == CeremonyDirection.SENT:
            sent_delta = actual_amount
            received_delta = 0
        else:
            sent_delta = 0
            received_delta = actual_amount

        await self._person_repo.update_totals(
            person_id=person.id,
            sent_delta=sent_delta,
            received_delta=received_delta,
            count_delta=1,
        )

    async def _rollback_ceremony_person_totals(
        self,
        user: User,
        transaction: Transaction,
        ceremony_event: "CeremonyEvent",
    ) -> None:
        """거래 삭제 시 CeremonyPerson 누적 금액과 이벤트 수를 차감한다."""
        person = await self._person_repo.get_or_create(
            user_id=user.id,
            name=ceremony_event.person_name,
            relationship=ceremony_event.relationship,
        )

        # Enum 인스턴스 직접 비교 (str, Enum 다중 상속으로 .value 불필요)
        if ceremony_event.direction == CeremonyDirection.SENT:
            sent_delta = -transaction.actual_amount
            received_delta = 0
        else:
            sent_delta = 0
            received_delta = -transaction.actual_amount

        await self._person_repo.update_totals(
            person_id=person.id,
            sent_delta=sent_delta,
            received_delta=received_delta,
            count_delta=-1,
        )
