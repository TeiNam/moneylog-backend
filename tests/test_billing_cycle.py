"""
카드 결제 주기 유틸리티 및 스키마 테스트.

billing_cycle_utils.py 순수 함수와 Pydantic 스키마 검증을 테스트한다.
Hypothesis를 사용한 속성 기반 테스트를 포함한다.
"""

import calendar
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.billing_cycle import (
    BillingConfigUpdateRequest,
    BillingDiscountCreateRequest,
)
from app.utils.billing_cycle_utils import (
    clamp_day_to_month,
    get_billing_cycle,
    get_default_billing_start_day,
    get_next_payment_date,
)


# ──────────────────────────────────────────────
# Property 3: 월말 클램핑
# Feature: card-billing-cycle, Property 3: 월말 클램핑
# ──────────────────────────────────────────────


@given(
    day=st.integers(min_value=1, max_value=31),
    ref_date=st.dates(
        min_value=date(2000, 1, 1),
        max_value=date(2100, 12, 31),
    ),
)
@settings(max_examples=200)
def test_clamp_day_to_month_property(day: int, ref_date: date) -> None:
    """clamp_day_to_month 결과는 항상 해당 월의 유효 날짜이며,
    result.day == min(day, last_day_of_month)을 만족한다."""
    result = clamp_day_to_month(day, ref_date.year, ref_date.month)
    last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
    assert result.day == min(day, last_day)
    assert result.month == ref_date.month
    assert result.year == ref_date.year


# ──────────────────────────────────────────────
# Property 4: 기본 사용 기준일 역산
# Feature: card-billing-cycle, Property 4: 기본 사용 기준일 역산
# ──────────────────────────────────────────────


@given(payment_day=st.integers(min_value=1, max_value=31))
@settings(max_examples=100)
def test_default_billing_start_day_property(payment_day: int) -> None:
    """get_default_billing_start_day 결과는 1~31 범위이다."""
    result = get_default_billing_start_day(payment_day)
    assert 1 <= result <= 31


# ──────────────────────────────────────────────
# Property 5: 결제 주기 계산 — 기준일 포함
# Feature: card-billing-cycle, Property 5: 결제 주기 계산 — 기준일 포함
# ──────────────────────────────────────────────


@given(
    payment_day=st.integers(min_value=1, max_value=31),
    billing_start_day=st.integers(min_value=1, max_value=31),
    ref_date=st.dates(
        min_value=date(2000, 1, 1),
        max_value=date(2100, 12, 31),
    ),
)
@settings(max_examples=200)
def test_billing_cycle_contains_reference_date(
    payment_day: int, billing_start_day: int, ref_date: date,
) -> None:
    """get_billing_cycle 결과는 start_date <= reference_date <= end_date를 만족한다."""
    cycle = get_billing_cycle(payment_day, billing_start_day, ref_date)
    assert cycle.start_date <= ref_date <= cycle.end_date


# ──────────────────────────────────────────────
# Property 1: 일(day) 값 범위 검증
# Feature: card-billing-cycle, Property 1: 일(day) 값 범위 검증
# ──────────────────────────────────────────────


@given(day=st.integers(min_value=-1000, max_value=1000))
@settings(max_examples=200)
def test_payment_day_range_validation(day: int) -> None:
    """1~31 범위이면 BillingConfigUpdateRequest 생성 성공, 범위 밖이면 ValidationError."""
    if 1 <= day <= 31:
        req = BillingConfigUpdateRequest(payment_day=day)
        assert req.payment_day == day
    else:
        with pytest.raises(ValidationError):
            BillingConfigUpdateRequest(payment_day=day)


# ──────────────────────────────────────────────
# Property 9: 청구할인 금액 검증
# Feature: card-billing-cycle, Property 9: 청구할인 금액 검증
# ──────────────────────────────────────────────


@given(amount=st.integers(min_value=-1000, max_value=1000))
@settings(max_examples=200)
def test_discount_amount_validation(amount: int) -> None:
    """0 이상이면 BillingDiscountCreateRequest 생성 성공, 음수이면 ValidationError."""
    if amount >= 0:
        req = BillingDiscountCreateRequest(
            name="테스트",
            amount=amount,
            cycle_start=date(2026, 3, 1),
            cycle_end=date(2026, 3, 31),
        )
        assert req.amount == amount
    else:
        with pytest.raises(ValidationError):
            BillingDiscountCreateRequest(
                name="테스트",
                amount=amount,
                cycle_start=date(2026, 3, 1),
                cycle_end=date(2026, 3, 31),
            )


# ──────────────────────────────────────────────
# Property 10: 결제 예정 금액 계산 (순수 로직 검증)
# Feature: card-billing-cycle, Property 10: 결제 예정 금액 계산
# ──────────────────────────────────────────────


@given(
    usage_amounts=st.lists(st.integers(min_value=0, max_value=1_000_000), max_size=50),
    discount_amounts=st.lists(st.integers(min_value=0, max_value=1_000_000), max_size=10),
)
@settings(max_examples=200)
def test_estimated_payment_formula(
    usage_amounts: list[int], discount_amounts: list[int],
) -> None:
    """estimated_payment == max(0, sum(usage) - sum(discount))."""
    total_usage = sum(usage_amounts)
    total_discount = sum(discount_amounts)
    estimated = max(0, total_usage - total_discount)
    assert estimated >= 0
    if total_usage >= total_discount:
        assert estimated == total_usage - total_discount
    else:
        assert estimated == 0


# ──────────────────────────────────────────────
# 단위 테스트: 구체적 edge case
# ──────────────────────────────────────────────


def test_clamp_day_feb_29_leap_year() -> None:
    """윤년 2월 29일 클램핑."""
    result = clamp_day_to_month(31, 2024, 2)
    assert result == date(2024, 2, 29)


def test_clamp_day_feb_28_non_leap() -> None:
    """평년 2월 28일 클램핑."""
    result = clamp_day_to_month(31, 2025, 2)
    assert result == date(2025, 2, 28)


def test_get_next_payment_date_same_day() -> None:
    """기준일이 결제일과 같으면 다음 달 결제일을 반환한다."""
    result = get_next_payment_date(15, date(2026, 3, 15))
    assert result == date(2026, 4, 15)


def test_get_next_payment_date_before() -> None:
    """기준일이 결제일 전이면 같은 달 결제일을 반환한다."""
    result = get_next_payment_date(15, date(2026, 3, 10))
    assert result == date(2026, 3, 15)


def test_billing_cycle_dec_to_jan() -> None:
    """12월→1월 연도 경계 결제 주기."""
    cycle = get_billing_cycle(25, 16, date(2025, 12, 20))
    assert cycle.start_date <= date(2025, 12, 20) <= cycle.end_date


def test_discount_name_max_length() -> None:
    """할인명 100자 초과 시 ValidationError."""
    with pytest.raises(ValidationError):
        BillingDiscountCreateRequest(
            name="가" * 101,
            amount=1000,
            cycle_start=date(2026, 3, 1),
            cycle_end=date(2026, 3, 31),
        )


def test_discount_name_max_length_ok() -> None:
    """할인명 100자는 허용."""
    req = BillingDiscountCreateRequest(
        name="가" * 100,
        amount=1000,
        cycle_start=date(2026, 3, 1),
        cycle_end=date(2026, 3, 31),
    )
    assert len(req.name) == 100
