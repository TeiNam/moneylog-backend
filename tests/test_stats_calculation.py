"""
순수 통계 계산 함수 단위 테스트 및 속성 기반 테스트.

calculate_change_rate, calculate_savings_rate, get_week_range 함수를 검증한다.
DB 없이 독립적으로 실행 가능하다.
"""

from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.stats_service import (
    calculate_change_rate,
    calculate_savings_rate,
    get_week_range,
)


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


def test_calculate_change_rate_normal():
    """전월 대비 증감률 정상 계산."""
    # 100 → 150: +50%
    assert calculate_change_rate(150, 100) == 50.0
    # 100 → 80: -20%
    assert calculate_change_rate(80, 100) == -20.0
    # 100 → 100: 0%
    assert calculate_change_rate(100, 100) == 0.0


def test_calculate_change_rate_previous_zero():
    """전월이 0일 때 None 반환."""
    assert calculate_change_rate(100, 0) is None
    assert calculate_change_rate(0, 0) is None


def test_calculate_savings_rate_normal():
    """저축률 정상 계산."""
    # 수입 1000, 지출 700 → 저축률 30%
    assert calculate_savings_rate(1000, 700) == 30.0
    # 수입 1000, 지출 0 → 저축률 100%
    assert calculate_savings_rate(1000, 0) == 100.0


def test_calculate_savings_rate_zero_income():
    """수입이 0일 때 0.0 반환."""
    assert calculate_savings_rate(0, 0) == 0.0
    assert calculate_savings_rate(0, 100) == 0.0


def test_get_week_range_monday():
    """월요일 입력 시 해당 주 월~일 반환."""
    # 2025-06-02는 월요일
    start, end = get_week_range(date(2025, 6, 2))
    assert start == date(2025, 6, 2)
    assert end == date(2025, 6, 8)
    assert start.weekday() == 0  # 월요일
    assert end.weekday() == 6  # 일요일


def test_get_week_range_wednesday():
    """수요일 입력 시 해당 주 월~일 반환."""
    # 2025-06-04는 수요일
    start, end = get_week_range(date(2025, 6, 4))
    assert start == date(2025, 6, 2)
    assert end == date(2025, 6, 8)


def test_get_week_range_sunday():
    """일요일 입력 시 해당 주 월~일 반환."""
    # 2025-06-08은 일요일
    start, end = get_week_range(date(2025, 6, 8))
    assert start == date(2025, 6, 2)
    assert end == date(2025, 6, 8)


# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════

# ──────────────────────────────────────────────
# Property 15: 주간 통계 날짜 범위
# Feature: moneylog-backend-phase5, Property 15: 주간 통계 날짜 범위
# Validates: Requirements 7.1
# ──────────────────────────────────────────────


@settings(max_examples=30)
@given(target_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
def test_property_week_range(target_date):
    """임의의 날짜에 대해 start_date는 월요일, end_date는 일요일, 차이 6일이어야 한다."""
    start, end = get_week_range(target_date)
    assert start.weekday() == 0  # 월요일
    assert end.weekday() == 6  # 일요일
    assert (end - start).days == 6
    assert start <= target_date <= end


# ──────────────────────────────────────────────
# Property 18: 전월 대비 증감률 계산
# Feature: moneylog-backend-phase5, Property 18: 전월 대비 증감률 계산
# Validates: Requirements 8.7, 8.8, 8.9
# ──────────────────────────────────────────────


@settings(max_examples=30)
@given(
    current=st.integers(min_value=0, max_value=100_000_000),
    previous=st.integers(min_value=0, max_value=100_000_000),
)
def test_property_change_rate(current, previous):
    """양수 전월 지출에 대해 증감률 = (당월 - 전월) / 전월 * 100, 전월 0이면 None."""
    result = calculate_change_rate(current, previous)
    if previous == 0:
        assert result is None
    else:
        expected = round((current - previous) / previous * 100, 1)
        assert result == expected


# ──────────────────────────────────────────────
# Property 21: 저축률 계산
# Feature: moneylog-backend-phase5, Property 21: 저축률 계산
# Validates: Requirements 9.6, 9.7
# ──────────────────────────────────────────────


@settings(max_examples=30)
@given(
    income=st.integers(min_value=0, max_value=100_000_000),
    expense=st.integers(min_value=0, max_value=100_000_000),
)
def test_property_savings_rate(income, expense):
    """양수 수입에 대해 저축률 = (수입 - 지출) / 수입 * 100, 수입 0이면 0.0."""
    result = calculate_savings_rate(income, expense)
    if income == 0:
        assert result == 0.0
    else:
        expected = round((income - expense) / income * 100, 1)
        assert result == expected
