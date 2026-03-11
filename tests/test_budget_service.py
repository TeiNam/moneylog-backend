"""
BudgetService 단위 테스트 및 속성 기반 테스트.

예산 CRUD, 연월 필터링, 예산 대비 실적, 권한 검증을 검증한다.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.budget import Budget
from app.repositories.budget_repository import BudgetRepository
from app.schemas.budget import (
    BudgetCreateRequest,
    BudgetPerformanceResponse,
    BudgetUpdateRequest,
)
from app.services.budget_service import BudgetService
from tests.conftest import create_test_user


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_budget(db_session):
    """예산 생성 정상 동작 검증."""
    user = await create_test_user(db_session)
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    data = BudgetCreateRequest(
        year=2025, month=6, category="식비", budget_amount=500000
    )
    budget = await service.create(user, data)

    assert budget.user_id == user.id
    assert budget.year == 2025
    assert budget.month == 6
    assert budget.category == "식비"
    assert budget.budget_amount == 500000
    assert budget.created_at is not None


@pytest.mark.asyncio
async def test_get_list_by_year_month(db_session):
    """연월 필터링 검증."""
    user = await create_test_user(db_session)
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    # 6월 예산 2개, 7월 예산 1개 생성
    await service.create(
        user, BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=500000)
    )
    await service.create(
        user, BudgetCreateRequest(year=2025, month=6, category="교통비", budget_amount=200000)
    )
    await service.create(
        user, BudgetCreateRequest(year=2025, month=7, category="식비", budget_amount=600000)
    )

    # 6월 필터링
    result = await service.get_list(user, 2025, 6)
    assert len(result) == 2
    assert all(b.year == 2025 and b.month == 6 for b in result)

    # 7월 필터링
    result = await service.get_list(user, 2025, 7)
    assert len(result) == 1
    assert result[0].month == 7


@pytest.mark.asyncio
async def test_update_budget(db_session):
    """예산 수정 정상 동작 검증."""
    user = await create_test_user(db_session)
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    budget = await service.create(
        user, BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=500000)
    )

    updated = await service.update(
        user, budget.id, BudgetUpdateRequest(budget_amount=600000)
    )

    assert updated.budget_amount == 600000
    assert updated.updated_at is not None


@pytest.mark.asyncio
async def test_delete_budget(db_session):
    """예산 삭제 정상 동작 검증."""
    user = await create_test_user(db_session)
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    budget = await service.create(
        user, BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=500000)
    )

    await service.delete(user, budget.id)

    # 삭제 후 조회 불가
    result = await repo.get_by_id(budget.id)
    assert result is None


@pytest.mark.asyncio
async def test_get_performance(db_session):
    """예산 대비 실적 계산 검증 (mock stats_repo)."""
    user = await create_test_user(db_session)
    repo = BudgetRepository(db_session)

    # stats_repo를 mock으로 생성
    mock_stats_repo = AsyncMock()
    mock_stats_repo.get_expense_by_category.return_value = [
        {"category": "식비", "amount": 300000},
        {"category": "교통비", "amount": 150000},
    ]

    service = BudgetService(repo, stats_repo=mock_stats_repo)

    # 예산 생성
    await service.create(
        user, BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=500000)
    )
    await service.create(
        user, BudgetCreateRequest(year=2025, month=6, category="교통비", budget_amount=200000)
    )

    result = await service.get_performance(user, 2025, 6)

    assert len(result) == 2

    # 식비: 500000 예산, 300000 실제 → 잔여 200000, 소진율 60.0%
    food = next(r for r in result if r.category == "식비")
    assert food.budget_amount == 500000
    assert food.actual_amount == 300000
    assert food.remaining == 200000
    assert food.usage_rate == 60.0

    # 교통비: 200000 예산, 150000 실제 → 잔여 50000, 소진율 75.0%
    transport = next(r for r in result if r.category == "교통비")
    assert transport.budget_amount == 200000
    assert transport.actual_amount == 150000
    assert transport.remaining == 50000
    assert transport.usage_rate == 75.0


@pytest.mark.asyncio
async def test_forbidden_error_on_other_user(db_session):
    """권한 없는 접근 시 ForbiddenError 검증."""
    user_a = await create_test_user(db_session, email="a@test.com", nickname="A")
    user_b = await create_test_user(db_session, email="b@test.com", nickname="B")
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    budget = await service.create(
        user_a, BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=500000)
    )

    # B가 A의 예산 수정 시도
    with pytest.raises(ForbiddenError):
        await service.update(user_b, budget.id, BudgetUpdateRequest(budget_amount=600000))

    # B가 A의 예산 삭제 시도
    with pytest.raises(ForbiddenError):
        await service.delete(user_b, budget.id)


@pytest.mark.asyncio
async def test_not_found_error_on_nonexistent(db_session):
    """존재하지 않는 예산 접근 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    fake_id = uuid.uuid4()

    with pytest.raises(NotFoundError):
        await service.update(user, fake_id, BudgetUpdateRequest(budget_amount=600000))

    with pytest.raises(NotFoundError):
        await service.delete(user, fake_id)


# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════

# Hypothesis 전략 정의
years = st.integers(min_value=2020, max_value=2030)
months = st.integers(min_value=1, max_value=12)
budget_amounts = st.integers(min_value=1, max_value=100_000_000)
categories = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)


# ──────────────────────────────────────────────
# Property 1: 예산 생성 라운드트립
# Feature: moneylog-backend-phase5, Property 1: 예산 생성 라운드트립
# Validates: Requirements 1.1, 1.2, 3.1, 3.2
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(year=years, month=months, amount=budget_amounts, category=categories)
async def test_property_budget_create_roundtrip(db_session, year, month, amount, category):
    """유효한 예산 데이터에 대해, create 후 모든 필드가 입력과 일치하고 user_id가 현재 사용자와 일치해야 한다."""
    user = await create_test_user(
        db_session, email=f"p1_{uuid.uuid4().hex[:8]}@test.com", nickname="P1"
    )
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    data = BudgetCreateRequest(
        year=year, month=month, category=category, budget_amount=amount
    )
    budget = await service.create(user, data)

    assert budget.user_id == user.id
    assert budget.year == year
    assert budget.month == month
    assert budget.category == category
    assert budget.budget_amount == amount
    assert budget.created_at is not None


# ──────────────────────────────────────────────
# Property 2: 예산 목록 연월 필터링
# Feature: moneylog-backend-phase5, Property 2: 예산 목록 연월 필터링
# Validates: Requirements 3.3
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    target_year=years,
    target_month=months,
    other_month=months,
)
async def test_property_budget_list_year_month_filter(
    db_session, target_year, target_month, other_month
):
    """다양한 연월의 예산에서 특정 year/month 필터 적용 시 해당 연월만 반환되어야 한다."""
    user = await create_test_user(
        db_session, email=f"p2_{uuid.uuid4().hex[:8]}@test.com", nickname="P2"
    )
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    # 대상 연월 예산 생성
    await service.create(
        user,
        BudgetCreateRequest(
            year=target_year, month=target_month, category="식비", budget_amount=100000
        ),
    )

    # 다른 연월 예산 생성 (다른 월이 같으면 다른 연도 사용)
    diff_year = target_year + 1 if target_month == other_month else target_year
    diff_month = other_month if target_month != other_month else other_month
    await service.create(
        user,
        BudgetCreateRequest(
            year=diff_year, month=diff_month, category="교통비", budget_amount=50000
        ),
    )

    result = await service.get_list(user, target_year, target_month)

    # 반환된 모든 예산의 year/month가 요청 값과 일치
    for b in result:
        assert b.year == target_year
        assert b.month == target_month
        assert b.user_id == user.id


# ──────────────────────────────────────────────
# Property 3: 예산 수정 시 updated_at 설정
# Feature: moneylog-backend-phase5, Property 3: 예산 수정 시 updated_at 설정
# Validates: Requirements 3.4
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(new_amount=budget_amounts)
async def test_property_budget_update_sets_updated_at(db_session, new_amount):
    """예산 수정 후 updated_at이 null이 아닌 값으로 설정되어야 한다."""
    user = await create_test_user(
        db_session, email=f"p3_{uuid.uuid4().hex[:8]}@test.com", nickname="P3"
    )
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    budget = await service.create(
        user,
        BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=500000),
    )

    updated = await service.update(
        user, budget.id, BudgetUpdateRequest(budget_amount=new_amount)
    )

    assert updated.updated_at is not None


# ──────────────────────────────────────────────
# Property 4: 예산 삭제 후 조회 불가
# Feature: moneylog-backend-phase5, Property 4: 예산 삭제 후 조회 불가
# Validates: Requirements 3.5
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(year=years, month=months, amount=budget_amounts)
async def test_property_budget_delete_then_not_found(db_session, year, month, amount):
    """예산 삭제 후 get_by_id가 None을 반환해야 한다."""
    user = await create_test_user(
        db_session, email=f"p4_{uuid.uuid4().hex[:8]}@test.com", nickname="P4"
    )
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    budget = await service.create(
        user,
        BudgetCreateRequest(year=year, month=month, category="식비", budget_amount=amount),
    )
    budget_id = budget.id

    await service.delete(user, budget_id)

    result = await repo.get_by_id(budget_id)
    assert result is None


# ──────────────────────────────────────────────
# Property 5: 리소스 접근 권한 검증
# Feature: moneylog-backend-phase5, Property 5: 리소스 접근 권한 검증
# Validates: Requirements 3.6, 5.9
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(amount=budget_amounts)
async def test_property_budget_permission_check(db_session, amount):
    """사용자 A가 소유한 예산을 사용자 B가 접근하면 ForbiddenError가 발생해야 한다."""
    user_a = await create_test_user(
        db_session, email=f"p5a_{uuid.uuid4().hex[:8]}@test.com", nickname="P5A"
    )
    user_b = await create_test_user(
        db_session, email=f"p5b_{uuid.uuid4().hex[:8]}@test.com", nickname="P5B"
    )
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    budget = await service.create(
        user_a,
        BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=amount),
    )

    # B가 A의 예산 수정 시도 → ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.update(
            user_b, budget.id, BudgetUpdateRequest(budget_amount=amount + 1)
        )

    # B가 A의 예산 삭제 시도 → ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.delete(user_b, budget.id)


# ──────────────────────────────────────────────
# Property 6: 존재하지 않는 리소스 접근 시 NotFoundError
# Feature: moneylog-backend-phase5, Property 6: 존재하지 않는 리소스 접근 시 NotFoundError
# Validates: Requirements 3.7, 5.10
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(data=st.uuids())
async def test_property_budget_not_found_error(db_session, data):
    """임의의 UUID로 존재하지 않는 예산에 접근하면 NotFoundError가 발생해야 한다."""
    user = await create_test_user(
        db_session, email=f"p6_{uuid.uuid4().hex[:8]}@test.com", nickname="P6"
    )
    repo = BudgetRepository(db_session)
    service = BudgetService(repo)

    with pytest.raises(NotFoundError):
        await service.update(
            user, data, BudgetUpdateRequest(budget_amount=100000)
        )

    with pytest.raises(NotFoundError):
        await service.delete(user, data)


# ──────────────────────────────────────────────
# Property 7: 예산 대비 실적 불변성
# Feature: moneylog-backend-phase5, Property 7: 예산 대비 실적 불변성
# Validates: Requirements 4.1, 4.2, 4.3, 4.4
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    budget_amt=budget_amounts,
    actual_amt=st.integers(min_value=0, max_value=100_000_000),
)
async def test_property_budget_performance_invariant(db_session, budget_amt, actual_amt):
    """예산 대비 실적에서 remaining = budget_amount - actual_amount, usage_rate = actual/budget*100 이어야 한다."""
    user = await create_test_user(
        db_session, email=f"p7_{uuid.uuid4().hex[:8]}@test.com", nickname="P7"
    )
    repo = BudgetRepository(db_session)

    # mock stats_repo: 카테고리별 실제 지출 반환
    mock_stats_repo = AsyncMock()
    mock_stats_repo.get_expense_by_category.return_value = [
        {"category": "식비", "amount": actual_amt},
    ]

    service = BudgetService(repo, stats_repo=mock_stats_repo)

    await service.create(
        user,
        BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=budget_amt),
    )

    result = await service.get_performance(user, 2025, 6)

    assert len(result) == 1
    perf = result[0]

    # remaining 불변성 검증
    assert perf.remaining == perf.budget_amount - perf.actual_amount

    # usage_rate 불변성 검증
    expected_rate = round(actual_amt / budget_amt * 100, 1) if budget_amt > 0 else 0.0
    assert perf.usage_rate == expected_rate
