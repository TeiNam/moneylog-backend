"""
SettlementService 단위 테스트 및 속성 기반 테스트.

가족 카드 사용 현황, 정산 계산, 접근 권한 검증을 검증한다.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import update as sa_update

from app.core.exceptions import BadRequestError
from app.models.family_group import FamilyGroup
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.stats_repository import StatsRepository
from app.repositories.user_repository import UserRepository
from app.services.settlement_service import SettlementService
from tests.conftest import create_test_user


# ══════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════


async def create_family_group(db):
    """테스트용 가족 그룹을 생성한다."""
    group = FamilyGroup(
        name="테스트 가족",
        invite_code=uuid.uuid4().hex[:8],
        invite_code_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        owner_id=uuid.uuid4(),
    )
    db.add(group)
    await db.flush()
    await db.refresh(group)
    return group


async def assign_family_group(db, user, group):
    """사용자를 가족 그룹에 할당한다."""
    await db.execute(
        sa_update(User).where(User.id == user.id).values(family_group_id=group.id)
    )
    await db.flush()
    await db.refresh(user)
    return user


async def create_transaction(
    db, user_id, tx_date, actual_amount=10000, family_group_id=None, asset_id=None
):
    """테스트용 거래를 생성한다."""
    tx = Transaction(
        user_id=user_id,
        family_group_id=family_group_id,
        date=tx_date,
        area="GENERAL",
        type="EXPENSE",
        major_category="식비",
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


# ══════════════════════════════════════════════
# Task 9.8: 단위 테스트
# ══════════════════════════════════════════════


class TestFamilyUsage:
    """가족 카드 사용 현황 단위 테스트."""

    @pytest.mark.asyncio
    async def test_family_usage_normal(self, db_session):
        """가족 카드 사용 현황 정상 동작 검증."""
        # 가족 그룹 생성
        group = await create_family_group(db_session)

        # 사용자 2명 생성 및 가족 그룹 할당
        user_a = await create_test_user(db_session, email="a@test.com", nickname="A")
        user_b = await create_test_user(db_session, email="b@test.com", nickname="B")
        user_a = await assign_family_group(db_session, user_a, group)
        user_b = await assign_family_group(db_session, user_b, group)

        # 거래 생성 (2025년 6월)
        asset_id = uuid.uuid4()
        await create_transaction(
            db_session, user_a.id, date(2025, 6, 10),
            actual_amount=50000, family_group_id=group.id, asset_id=asset_id,
        )
        await create_transaction(
            db_session, user_b.id, date(2025, 6, 15),
            actual_amount=30000, family_group_id=group.id, asset_id=asset_id,
        )
        await db_session.flush()

        # 서비스 호출
        stats_repo = StatsRepository(db_session)
        user_repo = UserRepository(db_session)
        service = SettlementService(stats_repo, user_repo)

        result = await service.get_family_usage(user_a, 2025, 6)

        # 검증
        assert result.year == 2025
        assert result.month == 6
        assert result.family_total_expense == 80000
        assert len(result.members) == 2

        # 구성원별 지출 확인
        member_map = {m.user_id: m for m in result.members}
        assert member_map[user_a.id].total_expense == 50000
        assert member_map[user_b.id].total_expense == 30000

    @pytest.mark.asyncio
    async def test_family_usage_no_group_raises_error(self, db_session):
        """family_group_id null 사용자 접근 시 BadRequestError 검증."""
        user = await create_test_user(db_session, email="solo@test.com")
        # family_group_id가 None인 상태

        stats_repo = StatsRepository(db_session)
        user_repo = UserRepository(db_session)
        service = SettlementService(stats_repo, user_repo)

        with pytest.raises(BadRequestError):
            await service.get_family_usage(user, 2025, 6)


class TestSettlementCalculation:
    """정산 계산 단위 테스트."""

    @pytest.mark.asyncio
    async def test_equal_split(self, db_session):
        """균등 분할 정산 정상 동작 검증."""
        group = await create_family_group(db_session)

        user_a = await create_test_user(db_session, email="eq_a@test.com", nickname="A")
        user_b = await create_test_user(db_session, email="eq_b@test.com", nickname="B")
        user_a = await assign_family_group(db_session, user_a, group)
        user_b = await assign_family_group(db_session, user_b, group)

        # A: 80000, B: 20000 → 총 100000, 균등 각 50000
        await create_transaction(
            db_session, user_a.id, date(2025, 6, 10),
            actual_amount=80000, family_group_id=group.id,
        )
        await create_transaction(
            db_session, user_b.id, date(2025, 6, 15),
            actual_amount=20000, family_group_id=group.id,
        )
        await db_session.flush()

        stats_repo = StatsRepository(db_session)
        user_repo = UserRepository(db_session)
        service = SettlementService(stats_repo, user_repo)

        result = await service.calculate_settlement(user_a, 2025, 6)

        assert result.family_total_expense == 100000
        assert result.split_method == "equal"
        assert len(result.members) == 2

        # 이체 검증: B가 A에게 30000 지불
        assert len(result.transfers) == 1
        assert result.transfers[0].amount == 30000

    @pytest.mark.asyncio
    async def test_ratio_split(self, db_session):
        """비율 분할 정산 정상 동작 검증."""
        group = await create_family_group(db_session)

        user_a = await create_test_user(db_session, email="rt_a@test.com", nickname="A")
        user_b = await create_test_user(db_session, email="rt_b@test.com", nickname="B")
        user_a = await assign_family_group(db_session, user_a, group)
        user_b = await assign_family_group(db_session, user_b, group)

        # A: 60000, B: 40000 → 총 100000, 비율 6:4 → A부담 60000, B부담 40000
        await create_transaction(
            db_session, user_a.id, date(2025, 6, 10),
            actual_amount=60000, family_group_id=group.id,
        )
        await create_transaction(
            db_session, user_b.id, date(2025, 6, 15),
            actual_amount=40000, family_group_id=group.id,
        )
        await db_session.flush()

        stats_repo = StatsRepository(db_session)
        user_repo = UserRepository(db_session)
        service = SettlementService(stats_repo, user_repo)

        result = await service.calculate_settlement(user_a, 2025, 6, ratio="6:4")

        assert result.family_total_expense == 100000
        assert "ratio" in result.split_method
        # 6:4 비율이면 차액 0 → 이체 없음
        assert len(result.transfers) == 0

    @pytest.mark.asyncio
    async def test_settlement_no_group_raises_error(self, db_session):
        """family_group_id null 사용자의 정산 요청 시 BadRequestError 검증."""
        user = await create_test_user(db_session, email="solo2@test.com")

        stats_repo = StatsRepository(db_session)
        user_repo = UserRepository(db_session)
        service = SettlementService(stats_repo, user_repo)

        with pytest.raises(BadRequestError):
            await service.calculate_settlement(user, 2025, 6)

    @pytest.mark.asyncio
    async def test_ratio_mismatch_raises_error(self, db_session):
        """ratio 비율 수 불일치 시 BadRequestError 검증."""
        group = await create_family_group(db_session)

        user_a = await create_test_user(db_session, email="mm_a@test.com", nickname="A")
        user_b = await create_test_user(db_session, email="mm_b@test.com", nickname="B")
        user_a = await assign_family_group(db_session, user_a, group)
        user_b = await assign_family_group(db_session, user_b, group)
        await db_session.flush()

        stats_repo = StatsRepository(db_session)
        user_repo = UserRepository(db_session)
        service = SettlementService(stats_repo, user_repo)

        # 2명인데 3개 비율 제공
        with pytest.raises(BadRequestError):
            await service.calculate_settlement(user_a, 2025, 6, ratio="5:3:2")


# ══════════════════════════════════════════════
# Task 9.9: Property 23 - 가족 지출 합계 불변성
# Feature: moneylog-backend-phase5, Property 23: 가족 지출 합계 불변성
# Validates: Requirements 10.1, 10.2, 10.3, 10.4
# ══════════════════════════════════════════════


class TestPropertyFamilyExpenseInvariance:
    """가족 지출 합계 불변성 속성 기반 테스트."""

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        amount_a=st.integers(min_value=1, max_value=10_000_000),
        amount_b=st.integers(min_value=1, max_value=10_000_000),
    )
    async def test_family_expense_sum_invariance(
        self, db_session, amount_a, amount_b
    ):
        """구성원별 total_expense 합 == family_total_expense,
        각 구성원의 total_expense == asset_expenses amount 합계."""
        # 가족 그룹 생성
        group = await create_family_group(db_session)

        user_a = await create_test_user(
            db_session,
            email=f"pa_{uuid.uuid4().hex[:8]}@test.com",
            nickname="PA",
        )
        user_b = await create_test_user(
            db_session,
            email=f"pb_{uuid.uuid4().hex[:8]}@test.com",
            nickname="PB",
        )
        user_a = await assign_family_group(db_session, user_a, group)
        user_b = await assign_family_group(db_session, user_b, group)

        asset_id = uuid.uuid4()
        await create_transaction(
            db_session, user_a.id, date(2025, 6, 10),
            actual_amount=amount_a, family_group_id=group.id, asset_id=asset_id,
        )
        await create_transaction(
            db_session, user_b.id, date(2025, 6, 15),
            actual_amount=amount_b, family_group_id=group.id, asset_id=asset_id,
        )
        await db_session.flush()

        stats_repo = StatsRepository(db_session)
        user_repo = UserRepository(db_session)
        service = SettlementService(stats_repo, user_repo)

        result = await service.get_family_usage(user_a, 2025, 6)

        # 불변성 1: 구성원별 total_expense 합 == family_total_expense
        member_total_sum = sum(m.total_expense for m in result.members)
        assert member_total_sum == result.family_total_expense

        # 불변성 2: 각 구성원의 total_expense == asset_expenses amount 합계
        for member in result.members:
            asset_sum = sum(ae.amount for ae in member.asset_expenses)
            assert member.total_expense == asset_sum


# ══════════════════════════════════════════════
# Task 9.10: Property 24 - 정산 접근 권한 검증
# Feature: moneylog-backend-phase5, Property 24: 정산 접근 권한 검증
# Validates: Requirements 10.5, 10.6, 11.8
# ══════════════════════════════════════════════


class TestPropertySettlementAccessControl:
    """정산 접근 권한 검증 속성 기반 테스트."""

    @pytest.mark.asyncio
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
        deadline=None,
    )
    @given(
        year=st.integers(min_value=2020, max_value=2030),
        month=st.integers(min_value=1, max_value=12),
    )
    async def test_no_family_group_raises_bad_request(
        self, db_session, year, month
    ):
        """family_group_id == None인 사용자의 정산 요청 시 BadRequestError 발생."""
        user = await create_test_user(
            db_session,
            email=f"nf_{uuid.uuid4().hex[:8]}@test.com",
            nickname="NoFamily",
        )
        # family_group_id가 None인 상태 확인
        assert user.family_group_id is None

        stats_repo = StatsRepository(db_session)
        user_repo = UserRepository(db_session)
        service = SettlementService(stats_repo, user_repo)

        # get_family_usage 접근 시 BadRequestError
        with pytest.raises(BadRequestError):
            await service.get_family_usage(user, year, month)

        # calculate_settlement 접근 시 BadRequestError
        with pytest.raises(BadRequestError):
            await service.calculate_settlement(user, year, month)
