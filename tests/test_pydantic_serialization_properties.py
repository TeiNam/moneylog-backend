"""
Pydantic 모델 직렬화 호환성 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 서비스 계층 반환 모델의
model_dump() 결과가 기존 dict 반환 구조와 동일한 키를 포함하는지 검증한다.

Feature: python-best-practices-improvements, Property 5: Pydantic 모델 직렬화 호환성
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.enums import (
    Area,
    CarType,
    CeremonyDirection,
    CeremonyEventType,
    TransactionSource,
    TransactionType,
)
from app.schemas.transaction import (
    CarExpenseDetailSchema,
    CeremonyEventSchema,
    TransactionDetailResult,
    TransactionResponse,
)
from app.schemas.transfer import TransferResponse, TransferWithAssetNames

# ---------------------------------------------------------------------------
# Hypothesis 전략 정의
# ---------------------------------------------------------------------------

# TransferResponse 생성을 위한 전략
_transfer_response_strategy = st.builds(
    TransferResponse,
    id=st.uuids(),
    user_id=st.uuids(),
    family_group_id=st.one_of(st.none(), st.uuids()),
    from_asset_id=st.uuids(),
    to_asset_id=st.uuids(),
    amount=st.integers(min_value=1, max_value=1_000_000_000),
    fee=st.integers(min_value=0, max_value=1_000_000),
    description=st.one_of(st.none(), st.text(min_size=0, max_size=50)),
    transfer_date=st.dates(),
    created_at=st.datetimes(),
    updated_at=st.one_of(st.none(), st.datetimes()),
)

# TransferWithAssetNames 생성을 위한 전략
_transfer_with_asset_names_strategy = st.builds(
    TransferWithAssetNames,
    transfer=_transfer_response_strategy,
    from_asset_name=st.text(min_size=1, max_size=30),
    to_asset_name=st.text(min_size=1, max_size=30),
)

# TransactionResponse 생성을 위한 전략
_transaction_response_strategy = st.builds(
    TransactionResponse,
    id=st.integers(min_value=1, max_value=2**63 - 1),
    user_id=st.uuids(),
    family_group_id=st.one_of(st.none(), st.uuids()),
    date=st.dates(),
    area=st.sampled_from([a.value for a in Area]),
    type=st.sampled_from([t.value for t in TransactionType]),
    major_category=st.text(min_size=1, max_size=20),
    minor_category=st.text(min_size=0, max_size=20),
    description=st.text(min_size=0, max_size=50),
    amount=st.integers(min_value=1, max_value=1_000_000_000),
    discount=st.integers(min_value=0, max_value=1_000_000),
    actual_amount=st.integers(min_value=0, max_value=1_000_000_000),
    asset_id=st.one_of(st.none(), st.uuids()),
    memo=st.one_of(st.none(), st.text(min_size=0, max_size=50)),
    source=st.sampled_from([s.value for s in TransactionSource]),
    created_at=st.datetimes(),
    updated_at=st.one_of(st.none(), st.datetimes()),
    is_private=st.booleans(),
)

# CarExpenseDetailSchema 전략
_car_detail_strategy = st.builds(
    CarExpenseDetailSchema,
    car_type=st.sampled_from(list(CarType)),
    fuel_amount_liter=st.one_of(st.none(), st.decimals(min_value=0, max_value=1000, places=2, allow_nan=False, allow_infinity=False)),
    fuel_unit_price=st.one_of(st.none(), st.integers(min_value=0, max_value=10000)),
    odometer=st.one_of(st.none(), st.integers(min_value=0, max_value=999999)),
    station_name=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
)

# CeremonyEventSchema 전략
_ceremony_event_strategy = st.builds(
    CeremonyEventSchema,
    direction=st.sampled_from(list(CeremonyDirection)),
    event_type=st.sampled_from(list(CeremonyEventType)),
    person_name=st.text(min_size=1, max_size=20),
    relationship=st.text(min_size=1, max_size=20),
    venue=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
)

# TransactionDetailResult 생성을 위한 전략 (car_detail, ceremony_event 포함)
_transaction_detail_result_strategy = st.builds(
    TransactionDetailResult,
    transaction=_transaction_response_strategy,
    car_detail=st.one_of(st.none(), _car_detail_strategy),
    ceremony_event=st.one_of(st.none(), _ceremony_event_strategy),
)


# ---------------------------------------------------------------------------
# Property 5: Pydantic 모델 직렬화 호환성
# Feature: python-best-practices-improvements, Property 5: Pydantic 모델 직렬화 호환성
# model_dump() 결과가 기존 dict 반환 구조와 동일한 키를 포함
# **Validates: 요구사항 3.5**
# ---------------------------------------------------------------------------


@settings(max_examples=30)
@given(model=_transfer_with_asset_names_strategy)
def test_transfer_with_asset_names_model_dump_contains_expected_keys(model: TransferWithAssetNames):
    """
    임의의 유효한 TransferWithAssetNames 모델에 대해
    model_dump() 결과는 기존 dict 반환 구조와 동일한 키
    ("transfer", "from_asset_name", "to_asset_name")를 포함해야 한다.

    **Validates: 요구사항 3.5**
    """
    # model_dump() 호출
    dumped = model.model_dump()

    # 기존 dict 반환 구조의 필수 키 검증
    expected_keys = {"transfer", "from_asset_name", "to_asset_name"}
    assert expected_keys.issubset(dumped.keys()), (
        f"누락된 키: {expected_keys - dumped.keys()}"
    )

    # 각 값의 타입 검증
    assert isinstance(dumped["transfer"], dict), "transfer 값은 dict여야 한다"
    assert isinstance(dumped["from_asset_name"], str), "from_asset_name 값은 str이어야 한다"
    assert isinstance(dumped["to_asset_name"], str), "to_asset_name 값은 str이어야 한다"


@settings(max_examples=30)
@given(model=_transaction_detail_result_strategy)
def test_transaction_detail_result_model_dump_contains_expected_keys(model: TransactionDetailResult):
    """
    임의의 유효한 TransactionDetailResult 모델에 대해
    model_dump() 결과는 기존 dict 반환 구조와 동일한 키
    ("transaction", "car_detail", "ceremony_event")를 포함해야 한다.

    **Validates: 요구사항 3.5**
    """
    # model_dump() 호출
    dumped = model.model_dump()

    # 기존 dict 반환 구조의 필수 키 검증
    expected_keys = {"transaction", "car_detail", "ceremony_event"}
    assert expected_keys.issubset(dumped.keys()), (
        f"누락된 키: {expected_keys - dumped.keys()}"
    )

    # transaction 값은 항상 dict여야 한다
    assert isinstance(dumped["transaction"], dict), "transaction 값은 dict여야 한다"

    # car_detail은 None 또는 dict
    assert dumped["car_detail"] is None or isinstance(dumped["car_detail"], dict), (
        "car_detail 값은 None 또는 dict여야 한다"
    )

    # ceremony_event는 None 또는 dict
    assert dumped["ceremony_event"] is None or isinstance(dumped["ceremony_event"], dict), (
        "ceremony_event 값은 None 또는 dict여야 한다"
    )


# ---------------------------------------------------------------------------
# Property 7: 필수 필드 누락 시 ValidationError
# Feature: python-best-practices-improvements, Property 7: 필수 필드 누락 시 ValidationError
# 필수 필드 하나를 제거하면 pydantic.ValidationError 발생
# **Validates: 요구사항 4.6**
# ---------------------------------------------------------------------------

import pydantic
import pytest

from app.schemas.transfer import TransferCreateData
from app.schemas.transaction import TransactionCreateData

# TransferCreateData 필수 필드 목록
_TRANSFER_REQUIRED_FIELDS = [
    "user_id",
    "from_asset_id",
    "to_asset_id",
    "amount",
    "transfer_date",
]

# TransactionCreateData 필수 필드 목록
_TRANSACTION_REQUIRED_FIELDS = [
    "user_id",
    "date",
    "area",
    "type",
    "major_category",
    "amount",
    "actual_amount",
    "source",
]


def _build_valid_transfer_data() -> dict:
    """유효한 TransferCreateData 딕셔너리를 생성한다."""
    return {
        "user_id": uuid4(),
        "family_group_id": None,
        "from_asset_id": uuid4(),
        "to_asset_id": uuid4(),
        "amount": 10000,
        "fee": 0,
        "description": None,
        "transfer_date": date.today(),
    }


def _build_valid_transaction_data() -> dict:
    """유효한 TransactionCreateData 딕셔너리를 생성한다."""
    return {
        "user_id": uuid4(),
        "family_group_id": None,
        "date": date.today(),
        "area": "FOOD",
        "type": "EXPENSE",
        "major_category": "식비",
        "minor_category": "",
        "description": "",
        "amount": 5000,
        "discount": 0,
        "actual_amount": 5000,
        "asset_id": None,
        "memo": None,
        "source": "MANUAL",
        "is_private": False,
    }


@settings(max_examples=30)
@given(field_to_remove=st.sampled_from(_TRANSFER_REQUIRED_FIELDS))
def test_transfer_create_data_missing_required_field_raises_validation_error(
    field_to_remove: str,
):
    """
    임의의 TransferCreateData 필수 필드 하나를 제거하면
    pydantic.ValidationError가 발생해야 한다.

    **Validates: 요구사항 4.6**
    """
    data = _build_valid_transfer_data()
    del data[field_to_remove]

    with pytest.raises(pydantic.ValidationError):
        TransferCreateData(**data)


@settings(max_examples=30)
@given(field_to_remove=st.sampled_from(_TRANSACTION_REQUIRED_FIELDS))
def test_transaction_create_data_missing_required_field_raises_validation_error(
    field_to_remove: str,
):
    """
    임의의 TransactionCreateData 필수 필드 하나를 제거하면
    pydantic.ValidationError가 발생해야 한다.

    **Validates: 요구사항 4.6**
    """
    data = _build_valid_transaction_data()
    del data[field_to_remove]

    with pytest.raises(pydantic.ValidationError):
        TransactionCreateData(**data)
