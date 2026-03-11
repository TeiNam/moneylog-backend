"""
SubscriptionService 단위 테스트 및 속성 기반 테스트.

구독 CRUD, 상태 필터링, 요약 계산, 권한 검증, 에러 케이스를 검증한다.
Property 1~6: 구독 생성 라운드트립, 상태 필터링, 수정 시 updated_at, 삭제 후 조회 불가,
접근 권한 검증, 존재하지 않는 리소스 접근 시 NotFoundError.
"""

import pytest
from datetime import date
from uuid import uuid4

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.enums import SubscriptionCategory, SubscriptionCycle, SubscriptionStatus
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.subscription_service import SubscriptionService
from app.schemas.subscription import SubscriptionCreateRequest, SubscriptionUpdateRequest
from app.core.exceptions import ForbiddenError, NotFoundError
from tests.conftest import create_test_user


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────

def _make_create_request(**overrides) -> SubscriptionCreateRequest:
    """기본 구독 생성 요청을 만드는 헬퍼."""
    defaults = {
        "service_name": "Netflix",
        "category": SubscriptionCategory.OTT,
        "amount": 17000,
        "cycle": SubscriptionCycle.MONTHLY,
        "billing_day": 15,
        "start_date": date(2025, 1, 1),
        "status": SubscriptionStatus.ACTIVE,
        "notify_before_days": 1,
    }
    defaults.update(overrides)
    return SubscriptionCreateRequest(**defaults)


async def _create_subscription(service, user, **overrides):
    """구독을 생성하고 반환하는 헬퍼."""
    req = _make_create_request(**overrides)
    return await service.create(user, req)


# ──────────────────────────────────────────────
# 단위 테스트: 구독 CRUD
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_subscription(db_session):
    """구독 생성 시 모든 필드가 올바르게 설정되는지 검증."""
    user = await create_test_user(db_session)
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    req = _make_create_request()
    sub = await service.create(user, req)

    assert sub.user_id == user.id
    assert sub.service_name == "Netflix"
    assert sub.category == "OTT"
    assert sub.amount == 17000
    assert sub.cycle == "MONTHLY"
    assert sub.billing_day == 15
    assert sub.status == "ACTIVE"
    assert sub.created_at is not None


@pytest.mark.asyncio
async def test_get_list(db_session):
    """구독 목록 조회가 정상 동작하는지 검증."""
    user = await create_test_user(db_session)
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    await _create_subscription(service, user, service_name="Netflix")
    await _create_subscription(service, user, service_name="Spotify", category=SubscriptionCategory.MUSIC)

    subs = await service.get_list(user)
    assert len(subs) == 2


@pytest.mark.asyncio
async def test_get_detail(db_session):
    """구독 상세 조회 시 다음 결제일이 포함되는지 검증."""
    user = await create_test_user(db_session)
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    sub = await _create_subscription(service, user)
    detail = await service.get_detail(user, sub.id)

    assert detail.id == sub.id
    assert detail.next_billing_date is not None


@pytest.mark.asyncio
async def test_update_subscription(db_session):
    """구독 수정 시 필드가 갱신되고 updated_at이 설정되는지 검증."""
    user = await create_test_user(db_session)
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    sub = await _create_subscription(service, user)
    update_req = SubscriptionUpdateRequest(service_name="Disney+", amount=9900)
    updated = await service.update(user, sub.id, update_req)

    assert updated.service_name == "Disney+"
    assert updated.amount == 9900
    assert updated.updated_at is not None


@pytest.mark.asyncio
async def test_delete_subscription(db_session):
    """구독 삭제 후 조회 시 None이 반환되는지 검증."""
    user = await create_test_user(db_session)
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    sub = await _create_subscription(service, user)
    await service.delete(user, sub.id)

    result = await repo.get_by_id(sub.id)
    assert result is None


# ──────────────────────────────────────────────
# 단위 테스트: 상태 필터링
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_list_with_status_filter(db_session):
    """상태 필터링이 올바르게 동작하는지 검증."""
    user = await create_test_user(db_session)
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    await _create_subscription(service, user, service_name="Active1", status=SubscriptionStatus.ACTIVE)
    await _create_subscription(service, user, service_name="Paused1", status=SubscriptionStatus.PAUSED)
    await _create_subscription(service, user, service_name="Cancelled1", status=SubscriptionStatus.CANCELLED)

    active_subs = await service.get_list(user, status=SubscriptionStatus.ACTIVE)
    assert len(active_subs) == 1
    assert all(s.status == "ACTIVE" for s in active_subs)

    paused_subs = await service.get_list(user, status=SubscriptionStatus.PAUSED)
    assert len(paused_subs) == 1
    assert all(s.status == "PAUSED" for s in paused_subs)


# ──────────────────────────────────────────────
# 단위 테스트: 요약 계산
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_summary(db_session):
    """구독 요약 계산이 올바른지 검증 (월 환산, 연환산, 활성 구독 수)."""
    user = await create_test_user(db_session)
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    # MONTHLY 17000원 → 월 17000원
    await _create_subscription(service, user, service_name="Netflix", amount=17000, cycle=SubscriptionCycle.MONTHLY)
    # YEARLY 120000원 → 월 10000원 (120000 // 12)
    await _create_subscription(service, user, service_name="iCloud", amount=120000, cycle=SubscriptionCycle.YEARLY)
    # WEEKLY 2500원 → 월 10000원 (2500 * 4)
    await _create_subscription(service, user, service_name="News", amount=2500, cycle=SubscriptionCycle.WEEKLY, category=SubscriptionCategory.NEWS)
    # PAUSED 구독은 요약에 포함되지 않음
    await _create_subscription(service, user, service_name="Paused", amount=5000, status=SubscriptionStatus.PAUSED)

    summary = await service.get_summary(user)

    assert summary.monthly_total == 37000  # 17000 + 10000 + 10000
    assert summary.yearly_total == 37000 * 12
    assert summary.active_count == 3


# ──────────────────────────────────────────────
# 단위 테스트: 권한 검증
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forbidden_error_on_other_user_access(db_session):
    """다른 사용자의 구독 접근 시 ForbiddenError가 발생하는지 검증."""
    user_a = await create_test_user(db_session, email="a@test.com", nickname="UserA")
    user_b = await create_test_user(db_session, email="b@test.com", nickname="UserB")
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    sub = await _create_subscription(service, user_a)

    # 상세 조회
    with pytest.raises(ForbiddenError):
        await service.get_detail(user_b, sub.id)

    # 수정
    with pytest.raises(ForbiddenError):
        await service.update(user_b, sub.id, SubscriptionUpdateRequest(service_name="Hacked"))

    # 삭제
    with pytest.raises(ForbiddenError):
        await service.delete(user_b, sub.id)


# ──────────────────────────────────────────────
# 단위 테스트: NotFoundError
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_not_found_error_on_nonexistent_subscription(db_session):
    """존재하지 않는 구독 접근 시 NotFoundError가 발생하는지 검증."""
    user = await create_test_user(db_session)
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)
    fake_id = uuid4()

    with pytest.raises(NotFoundError):
        await service.get_detail(user, fake_id)

    with pytest.raises(NotFoundError):
        await service.update(user, fake_id, SubscriptionUpdateRequest(service_name="X"))

    with pytest.raises(NotFoundError):
        await service.delete(user, fake_id)



# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════

# Hypothesis 전략 정의
subscription_categories = st.sampled_from(list(SubscriptionCategory))
subscription_cycles = st.sampled_from(list(SubscriptionCycle))
subscription_statuses = st.sampled_from(list(SubscriptionStatus))
billing_days = st.integers(min_value=1, max_value=31)
amounts = st.integers(min_value=1, max_value=10_000_000)
notify_before_days_st = st.integers(min_value=0, max_value=30)
service_names = st.text(
    min_size=1, max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), min_codepoint=65, max_codepoint=122),
)


# ──────────────────────────────────────────────
# Property 1: 구독 생성 라운드트립
# Feature: moneylog-backend-phase4, Property 1: 구독 생성 라운드트립
# Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    category=subscription_categories,
    cycle=subscription_cycles,
    billing_day=billing_days,
    amount=amounts,
)
async def test_property_create_roundtrip(db_session, category, cycle, billing_day, amount):
    """유효한 구독 생성 데이터에 대해, create 후 반환된 필드가 입력과 일치하고 user_id가 현재 사용자와 일치해야 한다."""
    user = await create_test_user(db_session, email=f"prop1_{uuid4().hex[:8]}@test.com", nickname="P1")
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    req = SubscriptionCreateRequest(
        service_name="TestService",
        category=category,
        amount=amount,
        cycle=cycle,
        billing_day=billing_day,
        start_date=date(2025, 1, 1),
        status=SubscriptionStatus.ACTIVE,
        notify_before_days=1,
    )
    sub = await service.create(user, req)

    # 모든 필드가 입력과 일치하는지 검증
    assert sub.user_id == user.id
    assert sub.service_name == "TestService"
    assert sub.category == category.value
    assert sub.amount == amount
    assert sub.cycle == cycle.value
    assert sub.billing_day == billing_day
    assert sub.status == SubscriptionStatus.ACTIVE.value
    assert sub.created_at is not None


# ──────────────────────────────────────────────
# Property 2: 구독 목록 상태 필터링
# Feature: moneylog-backend-phase4, Property 2: 구독 목록 상태 필터링
# Validates: Requirements 3.3, 3.4
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    filter_status=subscription_statuses,
    statuses=st.lists(subscription_statuses, min_size=1, max_size=5),
)
async def test_property_list_status_filter(db_session, filter_status, statuses):
    """다양한 상태의 구독 집합에서 status 필터 적용 시 해당 상태만 반환되어야 한다."""
    user = await create_test_user(db_session, email=f"prop2_{uuid4().hex[:8]}@test.com", nickname="P2")
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    # 다양한 상태의 구독 생성
    for i, status in enumerate(statuses):
        await _create_subscription(
            service, user,
            service_name=f"Svc{i}",
            status=status,
        )

    # 필터 적용 조회
    filtered = await service.get_list(user, status=filter_status)

    # 반환된 모든 구독의 status가 필터 값과 일치해야 함
    for sub in filtered:
        assert sub.status == filter_status.value
        assert sub.user_id == user.id


# ──────────────────────────────────────────────
# Property 3: 구독 수정 시 updated_at 설정
# Feature: moneylog-backend-phase4, Property 3: 구독 수정 시 updated_at 설정
# Validates: Requirements 3.5
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    new_amount=amounts,
)
async def test_property_update_sets_updated_at(db_session, new_amount):
    """구독 수정 후 updated_at이 null이 아닌 값으로 설정되어야 한다."""
    user = await create_test_user(db_session, email=f"prop3_{uuid4().hex[:8]}@test.com", nickname="P3")
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    sub = await _create_subscription(service, user)
    update_req = SubscriptionUpdateRequest(amount=new_amount)
    updated = await service.update(user, sub.id, update_req)

    assert updated.updated_at is not None


# ──────────────────────────────────────────────
# Property 4: 구독 삭제 후 조회 불가
# Feature: moneylog-backend-phase4, Property 4: 구독 삭제 후 조회 불가
# Validates: Requirements 3.6
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    category=subscription_categories,
    cycle=subscription_cycles,
)
async def test_property_delete_then_not_found(db_session, category, cycle):
    """구독 삭제 후 get_by_id가 None을 반환해야 한다."""
    user = await create_test_user(db_session, email=f"prop4_{uuid4().hex[:8]}@test.com", nickname="P4")
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    sub = await _create_subscription(service, user, category=category, cycle=cycle)
    sub_id = sub.id

    await service.delete(user, sub_id)

    result = await repo.get_by_id(sub_id)
    assert result is None


# ──────────────────────────────────────────────
# Property 5: 구독 접근 권한 검증
# Feature: moneylog-backend-phase4, Property 5: 구독 접근 권한 검증
# Validates: Requirements 3.7
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    category=subscription_categories,
)
async def test_property_permission_check(db_session, category):
    """User B가 User A의 구독에 접근하면 ForbiddenError가 발생해야 한다."""
    user_a = await create_test_user(db_session, email=f"propA_{uuid4().hex[:8]}@test.com", nickname="A")
    user_b = await create_test_user(db_session, email=f"propB_{uuid4().hex[:8]}@test.com", nickname="B")
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    sub = await _create_subscription(service, user_a, category=category)

    # 상세 조회 시 ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.get_detail(user_b, sub.id)

    # 수정 시 ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.update(user_b, sub.id, SubscriptionUpdateRequest(service_name="X"))

    # 삭제 시 ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.delete(user_b, sub.id)


# ──────────────────────────────────────────────
# Property 6: 존재하지 않는 리소스 접근 시 NotFoundError
# Feature: moneylog-backend-phase4, Property 6: 존재하지 않는 리소스 접근 시 NotFoundError
# Validates: Requirements 3.8, 8.4
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    data=st.data(),
)
async def test_property_not_found_error(db_session, data):
    """임의의 UUID로 구독에 접근하면 NotFoundError가 발생해야 한다."""
    user = await create_test_user(db_session, email=f"prop6_{uuid4().hex[:8]}@test.com", nickname="P6")
    repo = SubscriptionRepository(db_session)
    service = SubscriptionService(repo)

    fake_id = uuid4()

    with pytest.raises(NotFoundError):
        await service.get_detail(user, fake_id)

    with pytest.raises(NotFoundError):
        await service.update(user, fake_id, SubscriptionUpdateRequest(service_name="X"))

    with pytest.raises(NotFoundError):
        await service.delete(user, fake_id)
