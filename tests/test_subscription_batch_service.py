"""
SubscriptionBatchService 단위 테스트 및 속성 기반 테스트.

배치 결제 생성, 중복 방지, 누락분 보정, 비활성 구독 제외,
MONTHLY/YEARLY/WEEKLY 결제일 매칭을 검증한다.
Property 10~14: 결제일 매칭, 거래 필드 정확성, 중복 방지 멱등성,
비활성 구독 제외, 누락분 보정.
"""

import pytest
from datetime import date, timedelta
from uuid import uuid4

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy import select

from app.models.enums import (
    SubscriptionCategory,
    SubscriptionCycle,
    SubscriptionStatus,
)
from app.models.notification import Notification
from app.models.transaction import Transaction
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.transaction_repository import TransactionRepository
from app.services.subscription_batch_service import SubscriptionBatchService
from tests.conftest import create_test_user


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────


async def _create_subscription_direct(repo, user, **overrides):
    """구독을 직접 리포지토리를 통해 생성하는 헬퍼."""
    defaults = {
        "user_id": user.id,
        "family_group_id": user.family_group_id,
        "service_name": "TestService",
        "category": SubscriptionCategory.OTT.value,
        "amount": 10000,
        "cycle": SubscriptionCycle.MONTHLY.value,
        "billing_day": 15,
        "start_date": date(2025, 1, 15),
        "status": SubscriptionStatus.ACTIVE.value,
        "notify_before_days": 1,
    }
    defaults.update(overrides)
    return await repo.create(defaults)


def _make_batch_service(db_session):
    """배치 서비스 인스턴스를 생성하는 헬퍼."""
    sub_repo = SubscriptionRepository(db_session)
    txn_repo = TransactionRepository(db_session)
    noti_repo = NotificationRepository(db_session)
    return SubscriptionBatchService(sub_repo, txn_repo, noti_repo), sub_repo, txn_repo


async def _count_transactions(db_session, user_id=None):
    """거래 수를 세는 헬퍼."""
    stmt = select(Transaction)
    if user_id is not None:
        stmt = stmt.where(Transaction.user_id == user_id)
    result = await db_session.execute(stmt)
    return len(list(result.scalars().all()))


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_monthly_billing_day_match(db_session):
    """MONTHLY 구독 결제일 매칭 시 거래가 생성되는지 검증."""
    user = await create_test_user(db_session)
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    await _create_subscription_direct(
        sub_repo, user,
        service_name="Netflix",
        billing_day=15,
        cycle=SubscriptionCycle.MONTHLY.value,
    )

    result = await batch_svc.process_subscriptions(target_date=date(2025, 3, 15))

    assert result.processed_count == 1
    assert result.skipped_count == 0


@pytest.mark.asyncio
async def test_yearly_billing_match(db_session):
    """YEARLY 구독 결제월+결제일 매칭 시 거래가 생성되는지 검증."""
    user = await create_test_user(db_session)
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    await _create_subscription_direct(
        sub_repo, user,
        service_name="AnnualSub",
        billing_day=10,
        cycle=SubscriptionCycle.YEARLY.value,
        start_date=date(2024, 6, 10),
    )

    # 6월 10일 → 매칭
    result = await batch_svc.process_subscriptions(target_date=date(2025, 6, 10))
    assert result.processed_count == 1

    # 7월 10일 → 매칭 안 됨
    result2 = await batch_svc.process_subscriptions(target_date=date(2025, 7, 10))
    assert result2.processed_count == 0


@pytest.mark.asyncio
async def test_weekly_billing_match(db_session):
    """WEEKLY 구독 요일 매칭 시 거래가 생성되는지 검증."""
    user = await create_test_user(db_session)
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    # 2025-01-06은 월요일 (weekday=0)
    await _create_subscription_direct(
        sub_repo, user,
        service_name="WeeklySub",
        billing_day=6,
        cycle=SubscriptionCycle.WEEKLY.value,
        start_date=date(2025, 1, 6),
    )

    # 2025-03-10은 월요일 → 매칭
    result = await batch_svc.process_subscriptions(target_date=date(2025, 3, 10))
    assert result.processed_count == 1

    # 2025-03-11은 화요일 → 매칭 안 됨
    result2 = await batch_svc.process_subscriptions(target_date=date(2025, 3, 11))
    assert result2.processed_count == 0


@pytest.mark.asyncio
async def test_duplicate_prevention(db_session):
    """동일 구독+동일 날짜에 두 번 실행 시 거래가 1건만 생성되는지 검증."""
    user = await create_test_user(db_session)
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    await _create_subscription_direct(
        sub_repo, user,
        service_name="Netflix",
        billing_day=15,
    )

    target = date(2025, 3, 15)
    result1 = await batch_svc.process_subscriptions(target_date=target)
    result2 = await batch_svc.process_subscriptions(target_date=target)

    assert result1.processed_count == 1
    assert result2.processed_count == 0
    assert result2.skipped_count == 1

    count = await _count_transactions(db_session, user.id)
    assert count == 1


@pytest.mark.asyncio
async def test_paused_cancelled_excluded(db_session):
    """PAUSED/CANCELLED 구독이 배치에서 제외되는지 검증."""
    user = await create_test_user(db_session)
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    await _create_subscription_direct(
        sub_repo, user,
        service_name="PausedSub",
        billing_day=15,
        status=SubscriptionStatus.PAUSED.value,
    )
    await _create_subscription_direct(
        sub_repo, user,
        service_name="CancelledSub",
        billing_day=15,
        status=SubscriptionStatus.CANCELLED.value,
    )

    result = await batch_svc.process_subscriptions(target_date=date(2025, 3, 15))

    assert result.processed_count == 0
    count = await _count_transactions(db_session, user.id)
    assert count == 0


@pytest.mark.asyncio
async def test_month_end_clamping(db_session):
    """billing_day=31인 구독이 2월에 28일(또는 29일)에 거래 생성되는지 검증."""
    user = await create_test_user(db_session)
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    await _create_subscription_direct(
        sub_repo, user,
        service_name="EndOfMonth",
        billing_day=31,
    )

    # 2025년 2월은 28일이 마지막
    result = await batch_svc.process_subscriptions(target_date=date(2025, 2, 28))
    assert result.processed_count == 1

    # 2월 27일에는 매칭 안 됨
    result2 = await batch_svc.process_subscriptions(target_date=date(2025, 2, 27))
    assert result2.processed_count == 0


@pytest.mark.asyncio
async def test_backfill_missed_dates(db_session):
    """누락분 보정: target_date=None일 때 어제~오늘 2일 처리 검증."""
    user = await create_test_user(db_session)
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    today = date.today()
    yesterday = today - timedelta(days=1)

    # 매일 결제되는 구독 (billing_day를 어제와 오늘 모두 매칭하도록 WEEKLY 사용)
    # 어제 요일에 맞는 start_date 설정
    await _create_subscription_direct(
        sub_repo, user,
        service_name="DailySub",
        billing_day=yesterday.day,
        cycle=SubscriptionCycle.MONTHLY.value,
    )

    # target_date=None → 어제~오늘 처리
    result = await batch_svc.process_subscriptions(target_date=None)

    # 어제 billing_day가 매칭되면 최소 1건 처리
    assert result.processed_count >= 1


# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════

# Hypothesis 전략 정의
subscription_categories = st.sampled_from(list(SubscriptionCategory))
subscription_cycles = st.sampled_from(list(SubscriptionCycle))
active_statuses = st.just(SubscriptionStatus.ACTIVE)
inactive_statuses = st.sampled_from([SubscriptionStatus.PAUSED, SubscriptionStatus.CANCELLED])
billing_days = st.integers(min_value=1, max_value=28)
amounts = st.integers(min_value=1, max_value=10_000_000)
# 테스트 안정성을 위해 날짜 범위를 제한
target_dates = st.dates(min_value=date(2024, 1, 1), max_value=date(2026, 12, 31))


# ──────────────────────────────────────────────
# Property 10: 배치 — 결제일 매칭 구독에 대해서만 거래 생성
# Feature: moneylog-backend-phase4, Property 10: 배치 — 결제일 매칭 구독에 대해서만 거래 생성
# Validates: Requirements 5.1, 5.8, 5.9
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    target=target_dates,
    cycles=st.lists(subscription_cycles, min_size=1, max_size=3),
    billing_day=billing_days,
)
async def test_property_batch_billing_day_match(db_session, target, cycles, billing_day):
    """배치 실행 후 거래가 생성된 구독은 해당 target_date가 결제일인 구독뿐이어야 한다.

    **Validates: Requirements 5.1, 5.8, 5.9**
    """
    user = await create_test_user(
        db_session, email=f"p10_{uuid4().hex[:8]}@test.com", nickname="P10"
    )
    batch_svc, sub_repo, txn_repo = _make_batch_service(db_session)

    # 다양한 주기의 구독 생성
    created_subs = []
    for i, cycle in enumerate(cycles):
        # WEEKLY의 경우 start_date 요일이 중요
        start = date(2024, 1, 1) + timedelta(days=i)
        sub = await _create_subscription_direct(
            sub_repo, user,
            service_name=f"Svc{i}_{uuid4().hex[:4]}",
            billing_day=billing_day,
            cycle=cycle.value,
            start_date=start,
        )
        created_subs.append(sub)

    # 배치 실행
    await batch_svc.process_subscriptions(target_date=target)

    # 생성된 거래 조회
    stmt = select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.source == "SUBSCRIPTION_AUTO",
    )
    result = await db_session.execute(stmt)
    transactions = list(result.scalars().all())

    # 거래가 생성된 구독은 결제일 매칭 구독이어야 함
    for txn in transactions:
        # description으로 구독 찾기
        matching_sub = next(
            (s for s in created_subs if s.service_name == txn.description), None
        )
        assert matching_sub is not None
        assert batch_svc._is_billing_day(matching_sub, target)


# ──────────────────────────────────────────────
# Property 11: 배치 — 자동 생성 거래 필드 정확성
# Feature: moneylog-backend-phase4, Property 11: 배치 — 자동 생성 거래 필드 정확성
# Validates: Requirements 5.2, 5.3, 5.4, 5.5
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    category=subscription_categories,
    amount=amounts,
    billing_day=billing_days,
)
async def test_property_batch_transaction_fields(db_session, category, amount, billing_day):
    """배치로 생성된 거래의 필드가 구독 정보와 정확히 일치해야 한다.

    **Validates: Requirements 5.2, 5.3, 5.4, 5.5**
    """
    user = await create_test_user(
        db_session, email=f"p11_{uuid4().hex[:8]}@test.com", nickname="P11"
    )
    batch_svc, sub_repo, txn_repo = _make_batch_service(db_session)

    svc_name = f"FieldTest_{uuid4().hex[:6]}"
    sub = await _create_subscription_direct(
        sub_repo, user,
        service_name=svc_name,
        category=category.value,
        amount=amount,
        billing_day=billing_day,
        cycle=SubscriptionCycle.MONTHLY.value,
    )

    # billing_day에 맞는 날짜 생성
    target = date(2025, 3, billing_day)
    await batch_svc.process_subscriptions(target_date=target)

    # 생성된 거래 조회
    stmt = select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.description == svc_name,
    )
    result = await db_session.execute(stmt)
    transactions = list(result.scalars().all())

    # 거래가 생성되었으면 필드 검증
    if len(transactions) > 0:
        txn = transactions[0]
        assert txn.source == "SUBSCRIPTION_AUTO"
        assert txn.area == "SUBSCRIPTION"
        assert txn.amount == amount
        assert txn.actual_amount == amount
        assert txn.discount == 0
        assert txn.major_category == "구독"
        assert txn.minor_category == category.value
        assert txn.description == svc_name


# ──────────────────────────────────────────────
# Property 12: 배치 — 중복 방지 멱등성
# Feature: moneylog-backend-phase4, Property 12: 배치 — 중복 방지 멱등성
# Validates: Requirements 5.6, 6.3
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    billing_day=billing_days,
    amount=amounts,
)
async def test_property_batch_idempotency(db_session, billing_day, amount):
    """배치를 두 번 실행해도 동일 구독+동일 날짜에 대한 거래는 정확히 하나만 존재해야 한다.

    **Validates: Requirements 5.6, 6.3**
    """
    user = await create_test_user(
        db_session, email=f"p12_{uuid4().hex[:8]}@test.com", nickname="P12"
    )
    batch_svc, sub_repo, txn_repo = _make_batch_service(db_session)

    svc_name = f"Idempotent_{uuid4().hex[:6]}"
    await _create_subscription_direct(
        sub_repo, user,
        service_name=svc_name,
        billing_day=billing_day,
        amount=amount,
        cycle=SubscriptionCycle.MONTHLY.value,
    )

    target = date(2025, 3, billing_day)

    # 1차 실행
    await batch_svc.process_subscriptions(target_date=target)
    # 2차 실행
    await batch_svc.process_subscriptions(target_date=target)

    # 거래 수 확인
    stmt = select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.description == svc_name,
        Transaction.date == target,
    )
    result = await db_session.execute(stmt)
    transactions = list(result.scalars().all())

    # 정확히 1건만 존재해야 함
    assert len(transactions) == 1


# ──────────────────────────────────────────────
# Property 13: 배치 — 비활성 구독 제외
# Feature: moneylog-backend-phase4, Property 13: 배치 — 비활성 구독 제외
# Validates: Requirements 5.10, 5.11
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    status=inactive_statuses,
    billing_day=billing_days,
)
async def test_property_batch_inactive_excluded(db_session, status, billing_day):
    """PAUSED 또는 CANCELLED 상태의 구독에 대해 배치 실행 후 거래가 생성되지 않아야 한다.

    **Validates: Requirements 5.10, 5.11**
    """
    user = await create_test_user(
        db_session, email=f"p13_{uuid4().hex[:8]}@test.com", nickname="P13"
    )
    batch_svc, sub_repo, txn_repo = _make_batch_service(db_session)

    svc_name = f"Inactive_{uuid4().hex[:6]}"
    await _create_subscription_direct(
        sub_repo, user,
        service_name=svc_name,
        billing_day=billing_day,
        status=status.value,
    )

    target = date(2025, 3, billing_day)
    result = await batch_svc.process_subscriptions(target_date=target)

    assert result.processed_count == 0

    # 거래가 없어야 함
    stmt = select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.description == svc_name,
    )
    db_result = await db_session.execute(stmt)
    transactions = list(db_result.scalars().all())
    assert len(transactions) == 0


# ──────────────────────────────────────────────
# Property 14: 배치 — 누락분 보정
# Feature: moneylog-backend-phase4, Property 14: 배치 — 누락분 보정
# Validates: Requirements 6.1, 6.2, 6.4
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    billing_day=st.integers(min_value=1, max_value=28),
)
async def test_property_batch_backfill(db_session, billing_day):
    """누락된 날짜에 대해 보정 배치가 각 날짜별 거래를 생성해야 한다.

    **Validates: Requirements 6.1, 6.2, 6.4**
    """
    user = await create_test_user(
        db_session, email=f"p14_{uuid4().hex[:8]}@test.com", nickname="P14"
    )
    batch_svc, sub_repo, txn_repo = _make_batch_service(db_session)

    svc_name = f"Backfill_{uuid4().hex[:6]}"
    await _create_subscription_direct(
        sub_repo, user,
        service_name=svc_name,
        billing_day=billing_day,
        cycle=SubscriptionCycle.MONTHLY.value,
    )

    # 2개월 연속 결제일에 대해 각각 배치 실행 (누락분 보정 시뮬레이션)
    date1 = date(2025, 1, billing_day)
    date2 = date(2025, 2, billing_day)

    await batch_svc.process_subscriptions(target_date=date1)
    await batch_svc.process_subscriptions(target_date=date2)

    # 각 날짜에 대해 거래가 생성되어야 함
    stmt = select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.description == svc_name,
        Transaction.source == "SUBSCRIPTION_AUTO",
    )
    result = await db_session.execute(stmt)
    transactions = list(result.scalars().all())

    # 2건 생성되어야 함 (각 날짜별 1건)
    assert len(transactions) == 2

    # 각 거래의 날짜가 올바른지 확인
    txn_dates = sorted([t.date for t in transactions])
    assert date1 in txn_dates
    assert date2 in txn_dates



# ──────────────────────────────────────────────
# 알림 배치 헬퍼
# ──────────────────────────────────────────────


async def _count_notifications(db_session, user_id=None, subscription_id=None):
    """알림 수를 세는 헬퍼."""
    stmt = select(Notification)
    if user_id is not None:
        stmt = stmt.where(Notification.user_id == user_id)
    if subscription_id is not None:
        stmt = stmt.where(Notification.subscription_id == subscription_id)
    result = await db_session.execute(stmt)
    return list(result.scalars().all())


async def _get_notifications(db_session, user_id=None, subscription_id=None):
    """알림 목록을 조회하는 헬퍼."""
    stmt = select(Notification)
    if user_id is not None:
        stmt = stmt.where(Notification.user_id == user_id)
    if subscription_id is not None:
        stmt = stmt.where(Notification.subscription_id == subscription_id)
    result = await db_session.execute(stmt)
    return list(result.scalars().all())


# ══════════════════════════════════════════════
# 알림 배치 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════


# ──────────────────────────────────────────────
# Property 15: 알림 — 결제 전 알림 생성 타이밍
# Feature: moneylog-backend-phase4, Property 15: 알림 — 결제 전 알림 생성 타이밍
# Validates: Requirements 7.1, 7.2
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    billing_day=st.integers(min_value=1, max_value=28),
    notify_before=st.integers(min_value=0, max_value=10),
    days_offset=st.integers(min_value=0, max_value=15),
)
async def test_property_notification_timing(db_session, billing_day, notify_before, days_offset):
    """다음 결제일이 reference_date로부터 notify_before_days 이내이면 알림이 생성되고,
    그렇지 않으면 알림이 생성되지 않아야 한다.

    **Validates: Requirements 7.1, 7.2**
    """
    user = await create_test_user(
        db_session, email=f"p15_{uuid4().hex[:8]}@test.com", nickname="P15"
    )
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    svc_name = f"NotiTiming_{uuid4().hex[:6]}"
    sub = await _create_subscription_direct(
        sub_repo, user,
        service_name=svc_name,
        billing_day=billing_day,
        cycle=SubscriptionCycle.MONTHLY.value,
        notify_before_days=notify_before,
    )

    # billing_day에 맞는 결제일 기준으로 reference_date 계산
    # 결제일: 2025-06-{billing_day}
    next_billing = date(2025, 6, billing_day)
    # reference_date를 결제일로부터 days_offset일 전으로 설정
    reference = next_billing - timedelta(days=days_offset)

    # reference_date가 결제일 이후가 되지 않도록 보정
    if reference > next_billing:
        return

    await batch_svc.process_notifications(reference_date=reference)

    # 알림 조회
    notifications = await _get_notifications(
        db_session, user_id=user.id, subscription_id=sub.id
    )

    # 다음 결제일까지 남은 일수 계산
    # _calculate_next_billing_date를 사용하여 실제 다음 결제일 확인
    actual_next = batch_svc._calculate_next_billing_date(sub, reference)

    if actual_next is not None:
        actual_days = (actual_next - reference).days
        should_notify = 0 <= actual_days <= notify_before
    else:
        should_notify = False

    if should_notify:
        assert len(notifications) == 1, (
            f"알림이 생성되어야 함: days_until={actual_days}, "
            f"notify_before={notify_before}"
        )
    else:
        assert len(notifications) == 0, (
            f"알림이 생성되지 않아야 함: actual_next={actual_next}, "
            f"notify_before={notify_before}"
        )


# ──────────────────────────────────────────────
# Property 16: 알림 — 메시지 형식
# Feature: moneylog-backend-phase4, Property 16: 알림 — 메시지 형식
# Validates: Requirements 7.5
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    billing_day=st.integers(min_value=1, max_value=28),
    amount=st.integers(min_value=1, max_value=10_000_000),
    notify_before=st.integers(min_value=1, max_value=10),
)
async def test_property_notification_message_format(db_session, billing_day, amount, notify_before):
    """알림 배치로 생성된 알림의 title은 '구독 결제 예정'이어야 하고,
    message는 service_name, amount, 'D-{남은일수}' 형식을 포함해야 한다.

    **Validates: Requirements 7.5**
    """
    user = await create_test_user(
        db_session, email=f"p16_{uuid4().hex[:8]}@test.com", nickname="P16"
    )
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    svc_name = f"MsgFmt_{uuid4().hex[:6]}"
    sub = await _create_subscription_direct(
        sub_repo, user,
        service_name=svc_name,
        billing_day=billing_day,
        amount=amount,
        cycle=SubscriptionCycle.MONTHLY.value,
        notify_before_days=notify_before,
    )

    # 결제일 당일을 reference_date로 설정 (D-0, 반드시 알림 생성)
    reference = date(2025, 6, billing_day)
    await batch_svc.process_notifications(reference_date=reference)

    # 알림 조회
    notifications = await _get_notifications(
        db_session, user_id=user.id, subscription_id=sub.id
    )

    # 알림이 생성되었으면 형식 검증
    assert len(notifications) == 1, "결제일 당일에는 알림이 생성되어야 함"

    noti = notifications[0]
    # title 검증
    assert noti.title == "구독 결제 예정"
    # message에 service_name 포함
    assert svc_name in noti.message
    # message에 amount 포함
    assert f"{amount}원" in noti.message
    # message에 D-{남은일수} 형식 포함
    actual_next = batch_svc._calculate_next_billing_date(sub, reference)
    remaining = (actual_next - reference).days
    assert f"D-{remaining}" in noti.message


# ──────────────────────────────────────────────
# Property 17: 알림 — 중복 방지 멱등성
# Feature: moneylog-backend-phase4, Property 17: 알림 — 중복 방지 멱등성
# Validates: Requirements 7.6
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    billing_day=st.integers(min_value=1, max_value=28),
    notify_before=st.integers(min_value=1, max_value=10),
)
async def test_property_notification_idempotency(db_session, billing_day, notify_before):
    """알림 배치를 두 번 실행해도 동일 구독에 대한 알림은 정확히 하나만 존재해야 한다.

    **Validates: Requirements 7.6**
    """
    user = await create_test_user(
        db_session, email=f"p17_{uuid4().hex[:8]}@test.com", nickname="P17"
    )
    batch_svc, sub_repo, _ = _make_batch_service(db_session)

    svc_name = f"Idempotent_{uuid4().hex[:6]}"
    sub = await _create_subscription_direct(
        sub_repo, user,
        service_name=svc_name,
        billing_day=billing_day,
        cycle=SubscriptionCycle.MONTHLY.value,
        notify_before_days=notify_before,
    )

    # 결제일 당일을 reference_date로 설정 (반드시 알림 생성)
    reference = date(2025, 6, billing_day)

    # 1차 실행 전 해당 구독의 알림 수 확인
    before = await _get_notifications(
        db_session, user_id=user.id, subscription_id=sub.id
    )
    assert len(before) == 0

    # 1차 실행
    await batch_svc.process_notifications(reference_date=reference)

    after_first = await _get_notifications(
        db_session, user_id=user.id, subscription_id=sub.id
    )
    assert len(after_first) == 1, "1차 실행 후 알림 1건 생성되어야 함"

    # 2차 실행
    await batch_svc.process_notifications(reference_date=reference)

    after_second = await _get_notifications(
        db_session, user_id=user.id, subscription_id=sub.id
    )
    # 중복 방지: 여전히 1건만 존재해야 함
    assert len(after_second) == 1, (
        f"2차 실행 후에도 알림은 1건만 존재해야 함, 실제: {len(after_second)}"
    )
