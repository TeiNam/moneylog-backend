"""
다음 결제일 및 월 환산 금액 순수 함수 속성 기반 테스트.

Property 7: 월 환산 금액 계산
Property 8: 구독 요약 금액 불변성 (DB 사용)
Property 9: 다음 결제일 계산 — 항상 미래 또는 오늘
"""

import calendar
import pytest
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.enums import SubscriptionCategory, SubscriptionCycle, SubscriptionStatus
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.subscription_service import SubscriptionService
from app.schemas.subscription import SubscriptionCreateRequest
from tests.conftest import create_test_user


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────

def make_sub(cycle, amount, billing_day=15, start_date=date(2025, 1, 1)):
    """순수 함수 테스트용 mock 구독 객체를 생성한다."""
    return SimpleNamespace(
        cycle=cycle.value if hasattr(cycle, "value") else cycle,
        amount=amount,
        billing_day=billing_day,
        start_date=start_date,
    )


# ──────────────────────────────────────────────
# Hypothesis 전략 정의
# ──────────────────────────────────────────────

subscription_cycles = st.sampled_from(list(SubscriptionCycle))
subscription_categories = st.sampled_from(list(SubscriptionCategory))
amounts = st.integers(min_value=1, max_value=10_000_000)
billing_days = st.integers(min_value=1, max_value=31)
test_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))


# ══════════════════════════════════════════════
# Property 7: 월 환산 금액 계산
# Feature: moneylog-backend-phase4, Property 7: 월 환산 금액 계산
# Validates: Requirements 4.2
# ══════════════════════════════════════════════

@settings(max_examples=30)
@given(
    cycle=subscription_cycles,
    amount=amounts,
)
def test_property_monthly_amount_calculation(cycle, amount):
    """임의의 양수 amount와 SubscriptionCycle에 대해 월 환산 금액이 올바르게 계산되어야 한다."""
    service = SubscriptionService(subscription_repo=None)
    sub = make_sub(cycle=cycle, amount=amount)
    result = service.calculate_monthly_amount(sub)

    if cycle == SubscriptionCycle.MONTHLY:
        assert result == amount
    elif cycle == SubscriptionCycle.YEARLY:
        assert result == amount // 12
    elif cycle == SubscriptionCycle.WEEKLY:
        assert result == amount * 4


# ══════════════════════════════════════════════
# Property 8: 구독 요약 금액 불변성
# Feature: moneylog-backend-phase4, Property 8: 구독 요약 금액 불변성
# Validates: Requirements 4.1, 4.3
# ══════════════════════════════════════════════

@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    data=st.data(),
)
async def test_property_summary_invariant(db_session, data):
    """활성 구독 집합에 대해 yearly_total == monthly_total * 12이고 active_count가 ACTIVE 구독 수와 일치해야 한다."""
    user = await create_test_user(
        db_session,
        email=f"prop8_{uuid4().hex[:8]}@test.com",
        nickname="P8",
    )
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    # 랜덤 구독 생성 (1~5개)
    num_subs = data.draw(st.integers(min_value=1, max_value=5))
    active_count = 0

    for i in range(num_subs):
        cycle = data.draw(subscription_cycles)
        amount = data.draw(amounts)
        status = data.draw(st.sampled_from(list(SubscriptionStatus)))

        if status == SubscriptionStatus.ACTIVE:
            active_count += 1

        req = SubscriptionCreateRequest(
            service_name=f"Svc{i}",
            category=SubscriptionCategory.OTT,
            amount=amount,
            cycle=cycle,
            billing_day=15,
            start_date=date(2025, 1, 1),
            status=status,
            notify_before_days=1,
        )
        await service.create(user, req)

    # 요약 조회
    summary = await service.get_summary(user)

    # yearly_total == monthly_total * 12 불변성 검증
    assert summary.yearly_total == summary.monthly_total * 12
    # active_count 검증
    assert summary.active_count == active_count


# ══════════════════════════════════════════════
# Property 9: 다음 결제일 계산 — 항상 미래 또는 오늘
# Feature: moneylog-backend-phase4, Property 9: 다음 결제일 계산 — 항상 미래 또는 오늘
# Validates: Requirements 4.4, 4.5, 4.6, 4.7, 4.8
# ══════════════════════════════════════════════

@settings(max_examples=30)
@given(
    cycle=subscription_cycles,
    billing_day=billing_days,
    start_date=test_dates,
    reference_date=test_dates,
)
def test_property_next_billing_date_always_future_or_today(
    cycle, billing_day, start_date, reference_date
):
    """임의의 구독과 reference_date에 대해 다음 결제일이 항상 reference_date 이상이어야 한다."""
    service = SubscriptionService(subscription_repo=None)
    sub = make_sub(
        cycle=cycle,
        amount=10000,
        billing_day=billing_day,
        start_date=start_date,
    )

    result = service.calculate_next_billing_date(sub, reference_date)

    # 결과가 None이 아니어야 함
    assert result is not None

    # 결과가 reference_date 이상이어야 함
    assert result >= reference_date

    # 주기별 추가 검증
    if cycle == SubscriptionCycle.MONTHLY:
        # result.day == min(billing_day, 해당 월 마지막 날)
        last_day = calendar.monthrange(result.year, result.month)[1]
        expected_day = min(billing_day, last_day)
        assert result.day == expected_day

    elif cycle == SubscriptionCycle.YEARLY:
        # result.month == start_date.month
        assert result.month == start_date.month

    elif cycle == SubscriptionCycle.WEEKLY:
        # result.weekday() == start_date.weekday()
        assert result.weekday() == start_date.weekday()
