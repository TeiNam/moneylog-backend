"""결제 주기 계산을 위한 순수 함수 유틸리티 모듈.

상태를 갖지 않으며, 외부 의존성 없이 날짜 계산만 수행한다.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class BillingCycleInfo:
    """결제 주기 계산 결과를 담는 불변 값 객체."""

    start_date: date  # 결제 주기 시작일
    end_date: date  # 결제 주기 종료일
    payment_date: date  # 결제 예정일


def clamp_day_to_month(day: int, year: int, month: int) -> date:
    """지정된 일(day)을 해당 월의 유효 범위로 클램핑하여 date를 반환한다.

    day가 해당 월의 마지막 날보다 크면 마지막 날을 사용한다.
    예: day=31, month=2, year=2024 → date(2024, 2, 29)

    Args:
        day: 원하는 일 (1~31)
        year: 연도
        month: 월 (1~12)

    Returns:
        클램핑된 date 객체
    """
    last_day = calendar.monthrange(year, month)[1]
    clamped = min(day, last_day)
    return date(year, month, clamped)


def _next_month(year: int, month: int) -> tuple[int, int]:
    """다음 월의 (year, month)를 반환한다."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _prev_month(year: int, month: int) -> tuple[int, int]:
    """이전 월의 (year, month)를 반환한다."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def get_default_billing_start_day(payment_day: int) -> int:
    """결제일로부터 기본 사용 기준일을 역산한다.

    결제일 + 1일을 기본값으로 사용하며, 31을 초과하면 1로 순환한다.
    예: 결제일 15일 → 사용 기준일 16일
    예: 결제일 31일 → 사용 기준일 1일

    Args:
        payment_day: 결제일 (1~31)

    Returns:
        기본 사용 기준일 (1~31)
    """
    return (payment_day % 31) + 1


def get_next_payment_date(payment_day: int, reference_date: date) -> date:
    """기준일 이후의 다음 결제일을 계산한다.

    reference_date보다 엄격히 이후(strictly after)인 첫 번째 결제일을 반환한다.

    Args:
        payment_day: 결제일 (1~31)
        reference_date: 기준 날짜

    Returns:
        reference_date 이후의 다음 결제일 date
    """
    # 현재 월에서 결제일 클램핑
    candidate = clamp_day_to_month(
        payment_day, reference_date.year, reference_date.month
    )
    if candidate > reference_date:
        return candidate

    # 다음 월로 이동
    ny, nm = _next_month(reference_date.year, reference_date.month)
    return clamp_day_to_month(payment_day, ny, nm)


def _payment_date_for_cycle(payment_day: int, end_date: date) -> date:
    """결제 주기의 종료일에 대응하는 결제 예정일을 계산한다.

    end_date 이후(on or after)의 첫 번째 payment_day를 반환한다.

    Args:
        payment_day: 결제일 (1~31)
        end_date: 결제 주기 종료일

    Returns:
        결제 예정일 date
    """
    candidate = clamp_day_to_month(payment_day, end_date.year, end_date.month)
    if candidate >= end_date:
        return candidate

    # 종료일 이후 월로 이동
    ny, nm = _next_month(end_date.year, end_date.month)
    return clamp_day_to_month(payment_day, ny, nm)


def get_billing_cycle(
    payment_day: int,
    billing_start_day: int,
    reference_date: date,
) -> BillingCycleInfo:
    """기준일이 포함된 결제 주기(시작일, 종료일, 결제 예정일)를 계산한다.

    결제 주기는 billing_start_day부터 다음 billing_start_day 전일까지이다.
    반환되는 결과는 start_date <= reference_date <= end_date를 만족한다.

    Args:
        payment_day: 결제일 (1~31)
        billing_start_day: 사용 기준일 (1~31)
        reference_date: 기준 날짜

    Returns:
        BillingCycleInfo(start_date, end_date, payment_date)
    """
    # 현재 월의 billing_start_day 클램핑
    candidate_start = clamp_day_to_month(
        billing_start_day, reference_date.year, reference_date.month
    )

    if candidate_start <= reference_date:
        # 현재 월에서 주기가 시작됨
        start_date = candidate_start
        ny, nm = _next_month(reference_date.year, reference_date.month)
        next_start = clamp_day_to_month(billing_start_day, ny, nm)
        end_date = next_start - timedelta(days=1)
    else:
        # 이전 월에서 주기가 시작됨
        py, pm = _prev_month(reference_date.year, reference_date.month)
        start_date = clamp_day_to_month(billing_start_day, py, pm)
        end_date = candidate_start - timedelta(days=1)

    payment_date = _payment_date_for_cycle(payment_day, end_date)

    return BillingCycleInfo(
        start_date=start_date,
        end_date=end_date,
        payment_date=payment_date,
    )
