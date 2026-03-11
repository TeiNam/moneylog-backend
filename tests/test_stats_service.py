"""
StatsService 단위 테스트 및 속성 기반 테스트.

주간/월간/연간 통계 집계, 빈 데이터 처리, 사용자 데이터 격리를 검증한다.
"""

import uuid
from datetime import date, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models.transaction import Transaction
from app.repositories.budget_repository import BudgetRepository
from app.repositories.stats_repository import StatsRepository
from app.schemas.budget import BudgetCreateRequest
from app.services.budget_service import BudgetService
from app.services.stats_service import StatsService
from tests.conftest import create_test_user


# ══════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════


async def create_transaction(
    db,
    user_id,
    tx_date,
    tx_type="EXPENSE",
    area="GENERAL",
    major_category="식비",
    actual_amount=10000,
    asset_id=None,
    family_group_id=None,
):
    """테스트용 거래를 생성한다."""
    tx = Transaction(
        user_id=user_id,
        family_group_id=family_group_id,
        date=tx_date,
        area=area,
        type=tx_type,
        major_category=major_category,
        minor_category="기타",
        description="테스트 거래",
        amount=actual_amount,
        discount=0,
        actual_amount=actual_amount,
        asset_id=asset_id,
        source="MANUAL",
    )
    db.add(tx)
    await db.flush()
    return tx


# Hypothesis 전략 정의
transaction_amounts = st.integers(min_value=1, max_value=10_000_000)
areas = st.sampled_from(["GENERAL", "CAR", "SUBSCRIPTION", "EVENT"])
categories = st.sampled_from(["식비", "교통비", "문화생활", "의료비", "교육비"])


# ══════════════════════════════════════════════
# Task 8.7: 단위 테스트
# ══════════════════════════════════════════════


class TestWeeklyStats:
    """주간 통계 단위 테스트."""

    @pytest.mark.asyncio
    async def test_daily_expense_sums(self, db_session):
        """일별 지출 합계 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        # 2025-06-02(월) ~ 2025-06-08(일) 주간에 거래 생성
        await create_transaction(db_session, user.id, date(2025, 6, 2), actual_amount=5000)
        await create_transaction(db_session, user.id, date(2025, 6, 2), actual_amount=3000)
        await create_transaction(db_session, user.id, date(2025, 6, 4), actual_amount=10000)

        result = await service.get_weekly_stats(user, date(2025, 6, 3))

        assert len(result.daily_expenses) == 7
        assert result.start_date == date(2025, 6, 2)
        assert result.end_date == date(2025, 6, 8)
        # 월요일(6/2): 5000+3000=8000, 수요일(6/4): 10000
        assert result.daily_expenses[0].amount == 8000
        assert result.daily_expenses[2].amount == 10000
        assert result.total_expense == 18000

    @pytest.mark.asyncio
    async def test_no_spend_days(self, db_session):
        """무지출일 수 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        # 7일 중 2일만 지출
        await create_transaction(db_session, user.id, date(2025, 6, 2), actual_amount=5000)
        await create_transaction(db_session, user.id, date(2025, 6, 5), actual_amount=3000)

        result = await service.get_weekly_stats(user, date(2025, 6, 4))
        assert result.no_spend_days == 5

    @pytest.mark.asyncio
    async def test_area_breakdown(self, db_session):
        """영역별 비중 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(
            db_session, user.id, date(2025, 6, 2), area="GENERAL", actual_amount=7000
        )
        await create_transaction(
            db_session, user.id, date(2025, 6, 3), area="CAR", actual_amount=3000
        )

        result = await service.get_weekly_stats(user, date(2025, 6, 4))
        area_map = {a.area: a for a in result.area_breakdown}
        assert area_map["GENERAL"].amount == 7000
        assert area_map["CAR"].amount == 3000
        assert area_map["GENERAL"].ratio == 70.0
        assert area_map["CAR"].ratio == 30.0


class TestMonthlyStats:
    """월간 통계 단위 테스트."""

    @pytest.mark.asyncio
    async def test_income_expense_balance(self, db_session):
        """수입/지출/잔액 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(
            db_session, user.id, date(2025, 6, 1), tx_type="INCOME", actual_amount=3000000
        )
        await create_transaction(
            db_session, user.id, date(2025, 6, 10), tx_type="EXPENSE", actual_amount=500000
        )
        await create_transaction(
            db_session, user.id, date(2025, 6, 20), tx_type="EXPENSE", actual_amount=300000
        )

        result = await service.get_monthly_stats(user, 2025, 6)
        assert result.total_income == 3000000
        assert result.total_expense == 800000
        assert result.balance == 2200000

    @pytest.mark.asyncio
    async def test_category_breakdown(self, db_session):
        """카테고리별 비중 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(
            db_session, user.id, date(2025, 6, 5),
            major_category="식비", actual_amount=200000,
        )
        await create_transaction(
            db_session, user.id, date(2025, 6, 10),
            major_category="교통비", actual_amount=100000,
        )

        result = await service.get_monthly_stats(user, 2025, 6)
        cat_map = {c.category: c for c in result.category_breakdown}
        assert cat_map["식비"].amount == 200000
        assert cat_map["교통비"].amount == 100000

    @pytest.mark.asyncio
    async def test_budget_vs_actual(self, db_session):
        """예산 대비 실적 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        budget_service = BudgetService(budget_repo)
        service = StatsService(stats_repo, budget_repo)

        # 예산 설정
        await budget_service.create(
            user, BudgetCreateRequest(year=2025, month=6, category="식비", budget_amount=500000)
        )
        # 실제 지출
        await create_transaction(
            db_session, user.id, date(2025, 6, 5),
            major_category="식비", actual_amount=300000,
        )

        result = await service.get_monthly_stats(user, 2025, 6)
        assert len(result.budget_vs_actual) == 1
        bva = result.budget_vs_actual[0]
        assert bva.category == "식비"
        assert bva.budget_amount == 500000
        assert bva.actual_amount == 300000
        assert bva.remaining == 200000
        assert bva.usage_rate == 60.0

    @pytest.mark.asyncio
    async def test_prev_month_change_rate(self, db_session):
        """전월 대비 증감률 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        # 5월 지출
        await create_transaction(
            db_session, user.id, date(2025, 5, 15), actual_amount=200000
        )
        # 6월 지출
        await create_transaction(
            db_session, user.id, date(2025, 6, 15), actual_amount=300000
        )

        result = await service.get_monthly_stats(user, 2025, 6)
        # (300000 - 200000) / 200000 * 100 = 50.0
        assert result.prev_month_change_rate == 50.0

    @pytest.mark.asyncio
    async def test_prev_month_change_rate_none_when_zero(self, db_session):
        """전월 지출 0일 때 증감률 None 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        # 6월만 지출 (전월 없음)
        await create_transaction(
            db_session, user.id, date(2025, 6, 15), actual_amount=100000
        )

        result = await service.get_monthly_stats(user, 2025, 6)
        assert result.prev_month_change_rate is None

    @pytest.mark.asyncio
    async def test_asset_breakdown(self, db_session):
        """결제수단별 비중 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        asset_a = uuid.uuid4()
        asset_b = uuid.uuid4()
        await create_transaction(
            db_session, user.id, date(2025, 6, 5),
            actual_amount=60000, asset_id=asset_a,
        )
        await create_transaction(
            db_session, user.id, date(2025, 6, 10),
            actual_amount=40000, asset_id=asset_b,
        )

        result = await service.get_monthly_stats(user, 2025, 6)
        asset_map = {a.asset_id: a for a in result.asset_breakdown}
        assert asset_map[asset_a].amount == 60000
        assert asset_map[asset_b].amount == 40000
        assert asset_map[asset_a].ratio == 60.0
        assert asset_map[asset_b].ratio == 40.0


class TestYearlyStats:
    """연간 통계 단위 테스트."""

    @pytest.mark.asyncio
    async def test_monthly_trends(self, db_session):
        """월별 추이 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(
            db_session, user.id, date(2025, 1, 15),
            tx_type="INCOME", actual_amount=3000000,
        )
        await create_transaction(
            db_session, user.id, date(2025, 1, 20),
            tx_type="EXPENSE", actual_amount=500000,
        )
        await create_transaction(
            db_session, user.id, date(2025, 3, 10),
            tx_type="EXPENSE", actual_amount=200000,
        )

        result = await service.get_yearly_stats(user, 2025)
        assert len(result.monthly_trends) == 12
        # 1월: 수입 3000000, 지출 500000
        assert result.monthly_trends[0].income == 3000000
        assert result.monthly_trends[0].expense == 500000
        # 3월: 지출 200000
        assert result.monthly_trends[2].expense == 200000
        # 2월: 0
        assert result.monthly_trends[1].income == 0
        assert result.monthly_trends[1].expense == 0

    @pytest.mark.asyncio
    async def test_yearly_summary(self, db_session):
        """연간 요약 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(
            db_session, user.id, date(2025, 1, 15),
            tx_type="INCOME", actual_amount=5000000,
        )
        await create_transaction(
            db_session, user.id, date(2025, 6, 15),
            tx_type="INCOME", actual_amount=5000000,
        )
        await create_transaction(
            db_session, user.id, date(2025, 3, 10),
            tx_type="EXPENSE", actual_amount=2000000,
        )
        await create_transaction(
            db_session, user.id, date(2025, 9, 10),
            tx_type="EXPENSE", actual_amount=3000000,
        )

        result = await service.get_yearly_stats(user, 2025)
        assert result.total_income == 10000000
        assert result.total_expense == 5000000
        assert result.savings == 5000000
        assert result.savings_rate == 50.0

    @pytest.mark.asyncio
    async def test_top_categories(self, db_session):
        """TOP 카테고리 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(
            db_session, user.id, date(2025, 3, 10),
            major_category="식비", actual_amount=500000,
        )
        await create_transaction(
            db_session, user.id, date(2025, 6, 10),
            major_category="교통비", actual_amount=300000,
        )
        await create_transaction(
            db_session, user.id, date(2025, 9, 10),
            major_category="문화생활", actual_amount=200000,
        )

        result = await service.get_yearly_stats(user, 2025)
        assert len(result.top_categories) == 3
        # 내림차순 정렬 확인
        assert result.top_categories[0].category == "식비"
        assert result.top_categories[0].amount == 500000
        assert result.top_categories[1].category == "교통비"
        assert result.top_categories[2].category == "문화생활"


class TestEmptyData:
    """빈 데이터 처리 검증."""

    @pytest.mark.asyncio
    async def test_weekly_empty(self, db_session):
        """거래 없는 주간 통계 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        result = await service.get_weekly_stats(user, date(2025, 6, 4))
        assert result.total_expense == 0
        assert result.daily_average == 0
        assert result.no_spend_days == 7
        assert len(result.daily_expenses) == 7
        assert all(d.amount == 0 for d in result.daily_expenses)
        assert result.area_breakdown == []

    @pytest.mark.asyncio
    async def test_monthly_empty(self, db_session):
        """거래 없는 월간 통계 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        result = await service.get_monthly_stats(user, 2025, 6)
        assert result.total_income == 0
        assert result.total_expense == 0
        assert result.balance == 0
        assert result.category_breakdown == []
        assert result.asset_breakdown == []

    @pytest.mark.asyncio
    async def test_yearly_empty(self, db_session):
        """거래 없는 연간 통계 검증."""
        user = await create_test_user(db_session)
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        result = await service.get_yearly_stats(user, 2025)
        assert result.total_income == 0
        assert result.total_expense == 0
        assert result.savings == 0
        assert result.savings_rate == 0.0
        assert result.top_categories == []
        assert len(result.monthly_trends) == 12


class TestUserDataIsolation:
    """사용자 데이터 격리 검증."""

    @pytest.mark.asyncio
    async def test_weekly_isolation(self, db_session):
        """주간 통계에서 다른 사용자 데이터 미포함 검증."""
        user_a = await create_test_user(db_session, email="a@test.com", nickname="유저A")
        user_b = await create_test_user(db_session, email="b@test.com", nickname="유저B")
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(db_session, user_a.id, date(2025, 6, 2), actual_amount=10000)
        await create_transaction(db_session, user_b.id, date(2025, 6, 2), actual_amount=20000)

        result_a = await service.get_weekly_stats(user_a, date(2025, 6, 4))
        result_b = await service.get_weekly_stats(user_b, date(2025, 6, 4))

        assert result_a.total_expense == 10000
        assert result_b.total_expense == 20000

    @pytest.mark.asyncio
    async def test_monthly_isolation(self, db_session):
        """월간 통계에서 다른 사용자 데이터 미포함 검증."""
        user_a = await create_test_user(db_session, email="a@test.com", nickname="유저A")
        user_b = await create_test_user(db_session, email="b@test.com", nickname="유저B")
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(
            db_session, user_a.id, date(2025, 6, 10),
            tx_type="INCOME", actual_amount=1000000,
        )
        await create_transaction(
            db_session, user_b.id, date(2025, 6, 10),
            tx_type="INCOME", actual_amount=2000000,
        )

        result_a = await service.get_monthly_stats(user_a, 2025, 6)
        result_b = await service.get_monthly_stats(user_b, 2025, 6)

        assert result_a.total_income == 1000000
        assert result_b.total_income == 2000000

    @pytest.mark.asyncio
    async def test_yearly_isolation(self, db_session):
        """연간 통계에서 다른 사용자 데이터 미포함 검증."""
        user_a = await create_test_user(db_session, email="a@test.com", nickname="유저A")
        user_b = await create_test_user(db_session, email="b@test.com", nickname="유저B")
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        await create_transaction(
            db_session, user_a.id, date(2025, 3, 10), actual_amount=100000
        )
        await create_transaction(
            db_session, user_b.id, date(2025, 3, 10), actual_amount=200000
        )

        result_a = await service.get_yearly_stats(user_a, 2025)
        result_b = await service.get_yearly_stats(user_b, 2025)

        assert result_a.total_expense == 100000
        assert result_b.total_expense == 200000


# ══════════════════════════════════════════════
# Tasks 8.8~8.14: 속성 기반 테스트 (DB 기반)
# ══════════════════════════════════════════════


class TestPropertyWeeklyConsistency:
    """Property 14: 주간 통계 내부 일관성.

    daily_expenses length == 7,
    sum of daily amounts == total_expense,
    daily_average == total_expense // 7,
    no_spend_days == count of 0-amount days.

    **Validates: Requirements 7.2, 7.3, 7.4, 7.5**
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        amounts=st.lists(
            transaction_amounts, min_size=1, max_size=10
        ),
        day_offsets=st.lists(
            st.integers(min_value=0, max_value=6), min_size=1, max_size=10
        ),
    )
    async def test_weekly_internal_consistency(self, db_session, amounts, day_offsets):
        """주간 통계의 내부 일관성을 검증한다."""
        user = await create_test_user(
            db_session,
            email=f"weekly_{uuid.uuid4().hex[:8]}@test.com",
            nickname="주간테스트",
        )
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        # 2025-06-02(월) 기준 주간에 거래 생성
        base_monday = date(2025, 6, 2)
        for amt, offset in zip(amounts, day_offsets):
            tx_date = base_monday + timedelta(days=offset)
            await create_transaction(db_session, user.id, tx_date, actual_amount=amt)

        result = await service.get_weekly_stats(user, base_monday)

        # daily_expenses 길이 == 7
        assert len(result.daily_expenses) == 7

        # 일별 합계의 총합 == total_expense
        daily_sum = sum(d.amount for d in result.daily_expenses)
        assert daily_sum == result.total_expense

        # daily_average == total_expense // 7
        assert result.daily_average == result.total_expense // 7

        # no_spend_days == amount가 0인 날의 수
        zero_days = sum(1 for d in result.daily_expenses if d.amount == 0)
        assert result.no_spend_days == zero_days


class TestPropertyAreaBreakdownInvariance:
    """Property 16: 영역별 비중 합계 불변성.

    area_breakdown amount sum == total_expense,
    if total_expense > 0 then ratio sum ≈ 100%.

    **Validates: Requirements 7.6**
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        data=st.lists(
            st.tuples(areas, transaction_amounts),
            min_size=1,
            max_size=8,
        ),
    )
    async def test_area_breakdown_sum_invariance(self, db_session, data):
        """영역별 비중 합계 불변성을 검증한다."""
        user = await create_test_user(
            db_session,
            email=f"area_{uuid.uuid4().hex[:8]}@test.com",
            nickname="영역테스트",
        )
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        base_monday = date(2025, 6, 2)
        for i, (area, amt) in enumerate(data):
            tx_date = base_monday + timedelta(days=i % 7)
            await create_transaction(
                db_session, user.id, tx_date, area=area, actual_amount=amt
            )

        result = await service.get_weekly_stats(user, base_monday)

        # area_breakdown amount 합계 == total_expense
        area_amount_sum = sum(a.amount for a in result.area_breakdown)
        assert area_amount_sum == result.total_expense

        # 지출이 존재하면 ratio 합계 ≈ 100%
        if result.total_expense > 0:
            ratio_sum = sum(a.ratio for a in result.area_breakdown)
            assert abs(ratio_sum - 100.0) < 1.0


class TestPropertyMonthlyBalanceInvariance:
    """Property 17: 월간 통계 잔액 불변성.

    balance == total_income - total_expense.

    **Validates: Requirements 8.2, 8.3, 8.4**
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        incomes=st.lists(transaction_amounts, min_size=0, max_size=5),
        expenses=st.lists(transaction_amounts, min_size=0, max_size=5),
    )
    async def test_monthly_balance_invariance(self, db_session, incomes, expenses):
        """월간 통계의 잔액 불변성을 검증한다."""
        user = await create_test_user(
            db_session,
            email=f"balance_{uuid.uuid4().hex[:8]}@test.com",
            nickname="잔액테스트",
        )
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        for i, amt in enumerate(incomes):
            await create_transaction(
                db_session, user.id, date(2025, 6, min(i + 1, 28)),
                tx_type="INCOME", actual_amount=amt,
            )
        for i, amt in enumerate(expenses):
            await create_transaction(
                db_session, user.id, date(2025, 6, min(i + 1, 28)),
                tx_type="EXPENSE", actual_amount=amt,
            )

        result = await service.get_monthly_stats(user, 2025, 6)

        assert result.balance == result.total_income - result.total_expense


class TestPropertyBreakdownSumInvariance:
    """Property 19: 비중 합계 불변성.

    category_breakdown amount sum == total_expense,
    asset_breakdown amount sum == total_expense.

    **Validates: Requirements 8.5, 8.10**
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        data=st.lists(
            st.tuples(categories, transaction_amounts),
            min_size=1,
            max_size=8,
        ),
    )
    async def test_breakdown_sum_invariance(self, db_session, data):
        """카테고리별/결제수단별 비중 합계 불변성을 검증한다."""
        user = await create_test_user(
            db_session,
            email=f"breakdown_{uuid.uuid4().hex[:8]}@test.com",
            nickname="비중테스트",
        )
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        # 각 거래에 고유 asset_id 부여
        for i, (cat, amt) in enumerate(data):
            await create_transaction(
                db_session, user.id, date(2025, 6, min(i + 1, 28)),
                major_category=cat, actual_amount=amt,
                asset_id=uuid.uuid4(),
            )

        result = await service.get_monthly_stats(user, 2025, 6)

        # 카테고리별 amount 합계 == total_expense
        cat_sum = sum(c.amount for c in result.category_breakdown)
        assert cat_sum == result.total_expense

        # 결제수단별 amount 합계 == total_expense
        asset_sum = sum(a.amount for a in result.asset_breakdown)
        assert asset_sum == result.total_expense


class TestPropertyYearlySummaryInvariance:
    """Property 20: 연간 요약 불변성.

    monthly_trends income sum == total_income,
    expense sum == total_expense,
    savings == total_income - total_expense.

    **Validates: Requirements 9.2, 9.3, 9.4, 9.5**
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        income_months=st.lists(
            st.tuples(st.integers(min_value=1, max_value=12), transaction_amounts),
            min_size=0,
            max_size=6,
        ),
        expense_months=st.lists(
            st.tuples(st.integers(min_value=1, max_value=12), transaction_amounts),
            min_size=0,
            max_size=6,
        ),
    )
    async def test_yearly_summary_invariance(self, db_session, income_months, expense_months):
        """연간 요약 불변성을 검증한다."""
        user = await create_test_user(
            db_session,
            email=f"yearly_{uuid.uuid4().hex[:8]}@test.com",
            nickname="연간테스트",
        )
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        for month, amt in income_months:
            await create_transaction(
                db_session, user.id, date(2025, month, 15),
                tx_type="INCOME", actual_amount=amt,
            )
        for month, amt in expense_months:
            await create_transaction(
                db_session, user.id, date(2025, month, 15),
                tx_type="EXPENSE", actual_amount=amt,
            )

        result = await service.get_yearly_stats(user, 2025)

        # monthly_trends income 합계 == total_income
        trends_income = sum(t.income for t in result.monthly_trends)
        assert trends_income == result.total_income

        # monthly_trends expense 합계 == total_expense
        trends_expense = sum(t.expense for t in result.monthly_trends)
        assert trends_expense == result.total_expense

        # savings == total_income - total_expense
        assert result.savings == result.total_income - result.total_expense


class TestPropertyTopCategoriesSorted:
    """Property 22: TOP 카테고리 내림차순 정렬.

    top_categories is sorted by amount descending.

    **Validates: Requirements 9.8**
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        data=st.lists(
            st.tuples(categories, transaction_amounts),
            min_size=1,
            max_size=10,
        ),
    )
    async def test_top_categories_descending(self, db_session, data):
        """TOP 카테고리가 내림차순으로 정렬되어 있는지 검증한다."""
        user = await create_test_user(
            db_session,
            email=f"topcat_{uuid.uuid4().hex[:8]}@test.com",
            nickname="카테고리테스트",
        )
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        for i, (cat, amt) in enumerate(data):
            month = (i % 12) + 1
            await create_transaction(
                db_session, user.id, date(2025, month, 15),
                major_category=cat, actual_amount=amt,
            )

        result = await service.get_yearly_stats(user, 2025)

        # 내림차순 정렬 검증
        amounts = [c.amount for c in result.top_categories]
        assert amounts == sorted(amounts, reverse=True)


class TestPropertyUserDataIsolation:
    """Property 28: 사용자 데이터 격리.

    User A's transactions don't appear in User B's stats.

    **Validates: Requirements 7.7, 8.11, 9.11**
    """

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        amount_a=transaction_amounts,
        amount_b=transaction_amounts,
    )
    async def test_user_data_isolation(self, db_session, amount_a, amount_b):
        """사용자 A의 거래가 사용자 B의 통계에 포함되지 않는지 검증한다."""
        user_a = await create_test_user(
            db_session,
            email=f"iso_a_{uuid.uuid4().hex[:8]}@test.com",
            nickname="격리A",
        )
        user_b = await create_test_user(
            db_session,
            email=f"iso_b_{uuid.uuid4().hex[:8]}@test.com",
            nickname="격리B",
        )
        stats_repo = StatsRepository(db_session)
        budget_repo = BudgetRepository(db_session)
        service = StatsService(stats_repo, budget_repo)

        # 사용자 A, B 각각 거래 생성
        await create_transaction(
            db_session, user_a.id, date(2025, 6, 10), actual_amount=amount_a
        )
        await create_transaction(
            db_session, user_b.id, date(2025, 6, 10), actual_amount=amount_b
        )

        # 주간 통계 격리 검증
        weekly_a = await service.get_weekly_stats(user_a, date(2025, 6, 10))
        weekly_b = await service.get_weekly_stats(user_b, date(2025, 6, 10))
        assert weekly_a.total_expense == amount_a
        assert weekly_b.total_expense == amount_b

        # 월간 통계 격리 검증
        monthly_a = await service.get_monthly_stats(user_a, 2025, 6)
        monthly_b = await service.get_monthly_stats(user_b, 2025, 6)
        assert monthly_a.total_expense == amount_a
        assert monthly_b.total_expense == amount_b

        # 연간 통계 격리 검증
        yearly_a = await service.get_yearly_stats(user_a, 2025)
        yearly_b = await service.get_yearly_stats(user_b, 2025)
        assert yearly_a.total_expense == amount_a
        assert yearly_b.total_expense == amount_b
