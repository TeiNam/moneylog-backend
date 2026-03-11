"""
거래(Transaction) 서비스 단위 테스트.
**Validates: Requirements 2.1~2.9, 4.5, 4.6**
"""
from datetime import date
import pytest
from pydantic import ValidationError
from app.core.exceptions import ForbiddenError
from app.models.enums import (
    Area, CarType, CeremonyDirection,
    CeremonyEventType, TransactionType,
)
from app.repositories.ceremony_person_repository import CeremonyPersonRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import (
    CarExpenseDetailSchema, CeremonyEventSchema,
    TransactionCreateRequest,
)
from app.services.transaction_service import TransactionService
from tests.conftest import create_test_user


def _build_service(db_session) -> TransactionService:
    repo = TransactionRepository(db_session)
    person_repo = CeremonyPersonRepository(db_session)
    return TransactionService(repo, person_repo)


async def test_create_transaction_calculates_actual_amount(db_session):
    """actual_amount = amount - discount 자동 계산 검증."""
    user = await create_test_user(db_session, email="calc@test.com")
    await db_session.commit()
    service = _build_service(db_session)
    data = TransactionCreateRequest(
        date=date(2025, 1, 15), area=Area.GENERAL,
        type=TransactionType.EXPENSE, major_category="식비",
        amount=10000, discount=2000,
    )
    tx = await service.create(user, data)
    assert tx.actual_amount == 8000
    assert tx.amount == 10000
    assert tx.discount == 2000


async def test_create_car_transaction_creates_detail(db_session):
    """CAR 영역 거래 생성 시 CarExpenseDetail 레코드 생성 검증."""
    user = await create_test_user(db_session, email="car@test.com")
    await db_session.commit()
    service = _build_service(db_session)
    data = TransactionCreateRequest(
        date=date(2025, 2, 10), area=Area.CAR,
        type=TransactionType.EXPENSE, major_category="유류비",
        amount=50000,
        car_detail=CarExpenseDetailSchema(
            car_type=CarType.FUEL,
            fuel_amount_liter=30.5,
            fuel_unit_price=1650,
            station_name="테스트주유소",
        ),
    )
    tx = await service.create(user, data)
    repo = TransactionRepository(db_session)
    car_detail = await repo.get_car_detail_by_transaction_id(tx.id)
    assert car_detail is not None
    assert car_detail.transaction_id == tx.id
    assert car_detail.car_type == CarType.FUEL.value
    assert car_detail.station_name == "테스트주유소"


async def test_create_event_transaction_creates_ceremony_and_updates_person(db_session):
    """EVENT 영역 거래 생성 시 CeremonyEvent 생성 및 CeremonyPerson 누적 갱신 검증."""
    user = await create_test_user(db_session, email="event@test.com")
    await db_session.commit()
    service = _build_service(db_session)
    data = TransactionCreateRequest(
        date=date(2025, 3, 20), area=Area.EVENT,
        type=TransactionType.EXPENSE, major_category="경조사",
        amount=100000,
        ceremony_event=CeremonyEventSchema(
            direction=CeremonyDirection.SENT,
            event_type=CeremonyEventType.WEDDING,
            person_name="김철수", relationship="친구",
            venue="서울웨딩홀",
        ),
    )
    tx = await service.create(user, data)
    repo = TransactionRepository(db_session)
    event = await repo.get_ceremony_event_by_transaction_id(tx.id)
    assert event is not None
    assert event.person_name == "김철수"
    assert event.direction == CeremonyDirection.SENT.value
    person_repo = CeremonyPersonRepository(db_session)
    persons = await person_repo.search(user_id=user.id, query="김철수")
    assert len(persons) == 1
    person = persons[0]
    assert person.total_sent == 100000
    assert person.total_received == 0
    assert person.event_count == 1


def test_car_transaction_requires_car_detail():
    """CAR 영역 거래에서 car_detail 누락 시 ValidationError 발생 검증."""
    with pytest.raises(ValidationError, match="car_detail"):
        TransactionCreateRequest(
            date=date.today(), area=Area.CAR,
            type=TransactionType.EXPENSE,
            major_category="유류비", amount=50000,
        )


def test_event_transaction_requires_ceremony_event():
    """EVENT 영역 거래에서 ceremony_event 누락 시 ValidationError 발생 검증."""
    with pytest.raises(ValidationError, match="ceremony_event"):
        TransactionCreateRequest(
            date=date.today(), area=Area.EVENT,
            type=TransactionType.EXPENSE,
            major_category="경조사", amount=100000,
        )


async def test_delete_transaction_forbidden_for_other_user(db_session):
    """다른 사용자의 거래 삭제 시 ForbiddenError 발생 검증."""
    user_a = await create_test_user(db_session, email="owner@test.com")
    user_b = await create_test_user(db_session, email="other@test.com")
    await db_session.commit()
    service = _build_service(db_session)
    data = TransactionCreateRequest(
        date=date(2025, 4, 1), area=Area.GENERAL,
        type=TransactionType.EXPENSE,
        major_category="식비", amount=15000,
    )
    tx = await service.create(user_a, data)
    with pytest.raises(ForbiddenError):
        await service.delete(user_b, tx.id)
