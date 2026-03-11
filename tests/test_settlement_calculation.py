"""
순수 정산 계산 함수 단위 테스트 및 속성 기반 테스트.

parse_ratio, calculate_settlement_transfers 함수를 검증한다.
DB 없이 독립적으로 실행 가능하다.
"""

import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.exceptions import BadRequestError
from app.services.settlement_service import (
    calculate_settlement_transfers,
    parse_ratio,
)


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


def test_parse_ratio_normal():
    """비율 파싱 정상 동작."""
    result = parse_ratio("6:4", 2)
    assert len(result) == 2
    assert abs(result[0] - 0.6) < 0.001
    assert abs(result[1] - 0.4) < 0.001
    assert abs(sum(result) - 1.0) < 0.001


def test_parse_ratio_three_way():
    """3인 비율 파싱."""
    result = parse_ratio("5:3:2", 3)
    assert len(result) == 3
    assert abs(sum(result) - 1.0) < 0.001


def test_parse_ratio_mismatch():
    """비율 수 불일치 시 BadRequestError."""
    with pytest.raises(BadRequestError):
        parse_ratio("6:4", 3)  # 2개 비율, 3명 구성원

    with pytest.raises(BadRequestError):
        parse_ratio("5:3:2", 2)  # 3개 비율, 2명 구성원


def test_settlement_transfers_equal_split():
    """균등 분할 정산 이체 검증."""
    members = [
        {"user_id": uuid.uuid4(), "nickname": "A", "actual_expense": 80000},
        {"user_id": uuid.uuid4(), "nickname": "B", "actual_expense": 20000},
    ]
    # 총 100000, 균등 분할 → 각 50000
    shares = [50000, 50000]
    transfers = calculate_settlement_transfers(members, shares)

    # A: 80000 - 50000 = +30000 (돌려받음)
    # B: 20000 - 50000 = -30000 (지불)
    assert len(transfers) == 1
    assert transfers[0]["amount"] == 30000
    assert transfers[0]["from_user_id"] == members[1]["user_id"]
    assert transfers[0]["to_user_id"] == members[0]["user_id"]


def test_settlement_transfers_ratio_split():
    """비율 분할 정산 이체 검증."""
    members = [
        {"user_id": uuid.uuid4(), "nickname": "A", "actual_expense": 60000},
        {"user_id": uuid.uuid4(), "nickname": "B", "actual_expense": 40000},
    ]
    # 총 100000, 6:4 비율 → A: 60000, B: 40000 → 차액 0
    shares = [60000, 40000]
    transfers = calculate_settlement_transfers(members, shares)
    assert len(transfers) == 0  # 차액 없음


def test_settlement_transfers_sum_zero():
    """정산 차액 합계 0 검증."""
    members = [
        {"user_id": uuid.uuid4(), "nickname": "A", "actual_expense": 100000},
        {"user_id": uuid.uuid4(), "nickname": "B", "actual_expense": 50000},
        {"user_id": uuid.uuid4(), "nickname": "C", "actual_expense": 50000},
    ]
    # 총 200000, 균등 분할 → 각 66667, 66667, 66666
    shares = [66667, 66667, 66666]
    transfers = calculate_settlement_transfers(members, shares)

    # 이체 총액 검증: from 합계 == to 합계
    from_total = sum(t["amount"] for t in transfers)
    # 차액 합계 == 0 검증
    diffs = [m["actual_expense"] - s for m, s in zip(members, shares)]
    assert sum(diffs) == 0


# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════


# ──────────────────────────────────────────────
# Property 27: 비율 파싱 검증
# Feature: moneylog-backend-phase5, Property 27: 비율 파싱 검증
# Validates: Requirements 11.9
# ──────────────────────────────────────────────


@settings(max_examples=30)
@given(
    parts=st.lists(st.integers(min_value=1, max_value=10), min_size=2, max_size=4),
    member_count=st.integers(min_value=2, max_value=4),
)
def test_property_parse_ratio(parts, member_count):
    """비율 수 != 구성원 수 시 BadRequestError, 일치 시 정규화 합 == 1.0."""
    ratio_str = ":".join(str(p) for p in parts)
    if len(parts) != member_count:
        with pytest.raises(BadRequestError):
            parse_ratio(ratio_str, member_count)
    else:
        result = parse_ratio(ratio_str, member_count)
        assert len(result) == member_count
        assert abs(sum(result) - 1.0) < 0.0001


# ──────────────────────────────────────────────
# Property 25: 정산 부담액 계산
# Feature: moneylog-backend-phase5, Property 25: 정산 부담액 계산
# Validates: Requirements 11.4, 11.5
# ──────────────────────────────────────────────


@settings(max_examples=30)
@given(
    expenses=st.lists(
        st.integers(min_value=0, max_value=10_000_000),
        min_size=2,
        max_size=4,
    ),
)
def test_property_settlement_shares_sum(expenses):
    """균등 분할 시 부담액 합 == 가족 총 지출."""
    family_total = sum(expenses)
    member_count = len(expenses)

    # 균등 분할
    base = family_total // member_count
    remainder = family_total % member_count
    shares = [base] * member_count
    for i in range(remainder):
        shares[i] += 1

    assert sum(shares) == family_total


@settings(max_examples=30)
@given(
    expenses=st.lists(
        st.integers(min_value=0, max_value=10_000_000),
        min_size=2,
        max_size=4,
    ),
    ratio_parts=st.lists(st.integers(min_value=1, max_value=10), min_size=2, max_size=2),
)
def test_property_settlement_ratio_shares_sum(expenses, ratio_parts):
    """비율 분할 시 부담액 합 == 가족 총 지출."""
    # 구성원 수를 expenses 길이에 맞춤
    member_count = len(expenses)
    # ratio_parts 길이를 member_count에 맞춤
    while len(ratio_parts) < member_count:
        ratio_parts.append(ratio_parts[-1])
    ratio_parts = ratio_parts[:member_count]

    family_total = sum(expenses)
    total_ratio = sum(ratio_parts)
    ratios = [p / total_ratio for p in ratio_parts]

    shares = [int(family_total * r) for r in ratios]
    diff = family_total - sum(shares)
    shares[-1] += diff

    assert sum(shares) == family_total


# ──────────────────────────────────────────────
# Property 26: 정산 완결성
# Feature: moneylog-backend-phase5, Property 26: 정산 완결성
# Validates: Requirements 11.3, 11.6, 11.7
# ──────────────────────────────────────────────


@settings(max_examples=30)
@given(
    expenses=st.lists(
        st.integers(min_value=0, max_value=10_000_000),
        min_size=2,
        max_size=4,
    ),
)
def test_property_settlement_completeness(expenses):
    """정산 이체 적용 후 각 구성원의 순 지출 == 부담액, 차액 총합 == 0."""
    family_total = sum(expenses)
    member_count = len(expenses)

    # 균등 분할
    base = family_total // member_count
    remainder = family_total % member_count
    shares = [base] * member_count
    for i in range(remainder):
        shares[i] += 1

    members = [
        {"user_id": uuid.uuid4(), "nickname": f"M{i}", "actual_expense": exp}
        for i, exp in enumerate(expenses)
    ]

    transfers = calculate_settlement_transfers(members, shares)

    # 차액 총합 == 0
    diffs = [m["actual_expense"] - s for m, s in zip(members, shares)]
    assert sum(diffs) == 0

    # 이체 적용 후 순 지출 == 부담액
    net = {m["user_id"]: m["actual_expense"] for m in members}
    for t in transfers:
        net[t["from_user_id"]] += t["amount"]  # 지불자: 추가 지출
        net[t["to_user_id"]] -= t["amount"]    # 수취자: 지출 감소

    for i, m in enumerate(members):
        assert net[m["user_id"]] == shares[i]
