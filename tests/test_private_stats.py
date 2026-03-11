"""
비밀 거래 통계/정산 필터링 단위 테스트.

가족 그룹 통계에서 비밀 거래 제외, 가족 카드 사용 현황에서 비밀 거래 제외,
월간 정산에서 비밀 거래 제외, 개인 통계에서 비밀 거래 포함을 검증한다.
**Validates: Requirements 8.1, 8.2, 8.3, 8.4**
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import update as sa_update

from app.models.family_group import FamilyGroup
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.stats_repository import StatsRepository
from app.repositories.user_repository import UserRepository
from app.services.settlement_service import SettlementService
from tests.conftest import create_test_user


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────


async def _create_family_group(db_session, owner_id, name="테스트가족"):
    """테스트용 가족 그룹을 생성한다."""
    group = FamilyGroup(
        name=name,
        invite_code=uuid.uuid4().hex[:8],
        invite_code_expires_at=datetime(2030, 12, 31, tzinfo=timezone.utc),
        owner_id=owner_id,
    )
    db_session.add(group)
    await db_session.flush()
    await db_session.refresh(group)
    return group


async def _setup_family(db_session):
    """가족 그룹에 속한 두 사용자를 생성하여 반환한다."""
    user_a = await create_test_user(
        db_session,
        email=f"a_{uuid.uuid4().hex[:6]}@test.com",
        nickname="A",
    )
    user_b = await create_test_user(
        db_session,
        email=f"b_{uuid.uuid4().hex[:6]}@test.com",
        nickname="B",
    )
    group = await _create_family_group(db_session, owner_id=user_a.id)

    user_repo = UserRepository(db_session)
    await user_repo.update(user_a.id, {"family_group_id": group.id, "role_in_group": "OWNER"})
    await user_repo.update(user_b.id, {"family_group_id": group.id})
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    return user_a, user_b, group


async def _create_transaction(db_session, user_id, family_group_id=None, is_private=False, **overrides):
    """테스트용 거래를 생성한다."""
    defaults = {
        "user_id": user_id,
        "family_group_id": family_group_id,
        "date": date(2025, 6, 15),
        "area": "GENERAL",
        "type": "EXPENSE",
        "major_category": "식비",
        "minor_category": "외식",
        "description": "테스트",
        "amount": 10000,
        "discount": 0,
        "actual_amount": 10000,
        "source": "MANUAL",
        "is_private": is_private,
    }
    defaults.update(overrides)
    tx = Transaction(**defaults)
    db_session.add(tx)
    await db_session.flush()
    return tx


# ══════════════════════════════════════════════
# 단위 테스트: 비밀 거래 통계/정산 필터링
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_family_stats_excludes_private(db_session):
    """가족 그룹 통계에서 비밀 거래(is_private=true)가 제외되는지 검증한다.

    **Validates: Requirements 8.1**
    """
    user_a, user_b, group = await _setup_family(db_session)

    # 사용자 A: 공개 거래 10000 + 비밀 거래 5000
    await _create_transaction(
        db_session, user_a.id, family_group_id=group.id,
        is_private=False, actual_amount=10000,
    )
    await _create_transaction(
        db_session, user_a.id, family_group_id=group.id,
        is_private=True, actual_amount=5000,
    )
    # 사용자 B: 공개 거래 20000
    await _create_transaction(
        db_session, user_b.id, family_group_id=group.id,
        is_private=False, actual_amount=20000,
    )
    await db_session.flush()

    stats_repo = StatsRepository(db_session)
    result = await stats_repo.get_family_member_expenses(group.id, 2025, 6)

    # 사용자별 지출 매핑
    expense_map = {item["user_id"]: item["amount"] for item in result}

    # 사용자 A의 비밀 거래(5000)가 제외되어 10000만 집계
    assert expense_map[user_a.id] == 10000
    # 사용자 B는 공개 거래만 있으므로 20000
    assert expense_map[user_b.id] == 20000


@pytest.mark.asyncio
async def test_family_usage_excludes_private(db_session):
    """가족 카드 사용 현황에서 비밀 거래(is_private=true)가 제외되는지 검증한다.

    **Validates: Requirements 8.2**
    """
    user_a, user_b, group = await _setup_family(db_session)

    # 사용자 A: 공개 거래 10000 + 비밀 거래 5000
    await _create_transaction(
        db_session, user_a.id, family_group_id=group.id,
        is_private=False, actual_amount=10000, asset_id=uuid.uuid4(),
    )
    await _create_transaction(
        db_session, user_a.id, family_group_id=group.id,
        is_private=True, actual_amount=5000, asset_id=uuid.uuid4(),
    )
    # 사용자 B: 공개 거래 20000
    await _create_transaction(
        db_session, user_b.id, family_group_id=group.id,
        is_private=False, actual_amount=20000, asset_id=uuid.uuid4(),
    )
    await db_session.flush()

    stats_repo = StatsRepository(db_session)
    user_repo = UserRepository(db_session)
    service = SettlementService(stats_repo, user_repo)

    result = await service.get_family_usage(user_a, 2025, 6)

    # 사용자별 지출 확인
    member_map = {m.user_id: m for m in result.members}
    # 사용자 A: 비밀 거래 제외 → 10000
    assert member_map[user_a.id].total_expense == 10000
    # 사용자 B: 20000
    assert member_map[user_b.id].total_expense == 20000
    # 가족 총 지출: 10000 + 20000 = 30000 (비밀 거래 5000 제외)
    assert result.family_total_expense == 30000


@pytest.mark.asyncio
async def test_settlement_excludes_private(db_session):
    """월간 정산에서 비밀 거래(is_private=true)가 제외되는지 검증한다.

    **Validates: Requirements 8.3**
    """
    user_a, user_b, group = await _setup_family(db_session)

    # 사용자 A: 공개 거래 80000 + 비밀 거래 20000
    await _create_transaction(
        db_session, user_a.id, family_group_id=group.id,
        is_private=False, actual_amount=80000,
    )
    await _create_transaction(
        db_session, user_a.id, family_group_id=group.id,
        is_private=True, actual_amount=20000,
    )
    # 사용자 B: 공개 거래 20000
    await _create_transaction(
        db_session, user_b.id, family_group_id=group.id,
        is_private=False, actual_amount=20000,
    )
    await db_session.flush()

    stats_repo = StatsRepository(db_session)
    user_repo = UserRepository(db_session)
    service = SettlementService(stats_repo, user_repo)

    result = await service.calculate_settlement(user_a, 2025, 6)

    # 가족 총 지출: 80000 + 20000 = 100000 (비밀 거래 20000 제외)
    assert result.family_total_expense == 100000
    # 균등 분할: 각 50000
    # A 실제 80000, B 실제 20000 → B가 A에게 30000 이체
    assert len(result.transfers) == 1
    assert result.transfers[0].amount == 30000


@pytest.mark.asyncio
async def test_personal_stats_includes_private(db_session):
    """개인 통계에서 비밀 거래(is_private=true)가 포함되는지 검증한다.

    **Validates: Requirements 8.4**
    """
    user = await create_test_user(
        db_session,
        email=f"personal_{uuid.uuid4().hex[:6]}@test.com",
        nickname="개인",
    )

    # 공개 거래 10000 + 비밀 거래 5000
    await _create_transaction(
        db_session, user.id,
        is_private=False, actual_amount=10000,
    )
    await _create_transaction(
        db_session, user.id,
        is_private=True, actual_amount=5000,
    )
    await db_session.flush()

    stats_repo = StatsRepository(db_session)
    result = await stats_repo.get_expense_sum_by_date_range(
        user.id, date(2025, 6, 1), date(2025, 6, 30)
    )

    # 개인 통계는 비밀 거래 포함 → 10000 + 5000 = 15000
    assert result == 15000


# ══════════════════════════════════════════════
# 속성 기반 테스트: 가족 집계 시 비밀 거래 제외
# Feature: moneylog-backend-phase6, Property 12: 가족 집계 시 비밀 거래 제외
# ══════════════════════════════════════════════

from hypothesis import given, settings, strategies as st

from app.repositories.user_repository import UserRepository as _UserRepo


@pytest.mark.asyncio
async def test_pbt_family_aggregation_excludes_private(db_session):
    """Property 12: 가족 집계 시 비밀 거래 제외.

    *For any* 가족 그룹과 비밀/공개 거래가 혼합된 거래 집합에 대해,
    가족 그룹 통계, 가족 카드 사용 현황, 월간 정산 계산 시
    is_private=true인 거래의 금액이 집계에 포함되지 않아야 한다.

    # Feature: moneylog-backend-phase6, Property 12: 가족 집계 시 비밀 거래 제외
    **Validates: Requirements 8.1, 8.2, 8.3**
    """

    # Hypothesis로 테스트 케이스 동기 생성
    cases: list[tuple[list[int], list[bool]]] = []

    @given(
        amounts=st.lists(
            st.integers(min_value=1, max_value=1_000_000),
            min_size=1,
            max_size=5,
        ),
        private_flags=st.lists(st.booleans(), min_size=1, max_size=5),
    )
    @settings(max_examples=30)
    def generate(amounts, private_flags):
        # 두 리스트 길이를 맞춤 (짧은 쪽 기준)
        min_len = min(len(amounts), len(private_flags))
        cases.append((amounts[:min_len], private_flags[:min_len]))

    generate()

    for amounts, private_flags in cases:
        # 가족 그룹 및 두 사용자 생성
        user_a, user_b, group = await _setup_family(db_session)

        # 사용자 A의 거래 생성 (비밀/공개 혼합)
        for amt, is_priv in zip(amounts, private_flags):
            await _create_transaction(
                db_session,
                user_a.id,
                family_group_id=group.id,
                is_private=is_priv,
                actual_amount=amt,
                amount=amt,
                asset_id=uuid.uuid4(),
            )

        # 사용자 B의 공개 거래 1건 (기준점)
        b_amount = 1000
        await _create_transaction(
            db_session,
            user_b.id,
            family_group_id=group.id,
            is_private=False,
            actual_amount=b_amount,
            amount=b_amount,
            asset_id=uuid.uuid4(),
        )
        await db_session.flush()

        # 공개 거래 금액 합계 계산
        expected_public_sum = sum(
            amt for amt, priv in zip(amounts, private_flags) if not priv
        )

        # ── 검증 1: 가족 그룹 통계 (get_family_member_expenses) ──
        stats_repo = StatsRepository(db_session)
        family_expenses = await stats_repo.get_family_member_expenses(
            group.id, 2025, 6
        )
        expense_map = {item["user_id"]: item["amount"] for item in family_expenses}

        a_stat = expense_map.get(user_a.id, 0)
        assert a_stat == expected_public_sum, (
            f"가족 통계: 사용자 A 집계 {a_stat} != 공개 합계 {expected_public_sum}"
        )

        # ── 검증 2: 가족 카드 사용 현황 (get_family_usage) ──
        user_repo = _UserRepo(db_session)
        settlement_svc = SettlementService(stats_repo, user_repo)
        usage = await settlement_svc.get_family_usage(user_a, 2025, 6)

        member_map = {m.user_id: m for m in usage.members}
        a_usage = member_map[user_a.id].total_expense
        assert a_usage == expected_public_sum, (
            f"가족 사용 현황: 사용자 A 지출 {a_usage} != 공개 합계 {expected_public_sum}"
        )
        # 가족 총 지출에도 비밀 거래 미포함
        assert usage.family_total_expense == expected_public_sum + b_amount, (
            f"가족 총 지출 {usage.family_total_expense} != "
            f"공개 합계 {expected_public_sum} + B {b_amount}"
        )

        # ── 검증 3: 월간 정산 (calculate_settlement) ──
        settlement = await settlement_svc.calculate_settlement(user_a, 2025, 6)
        assert settlement.family_total_expense == expected_public_sum + b_amount, (
            f"정산 총 지출 {settlement.family_total_expense} != "
            f"공개 합계 {expected_public_sum} + B {b_amount}"
        )

        # 정산 후 롤백하여 다음 케이스에 영향 없도록 함
        await db_session.rollback()


# ══════════════════════════════════════════════
# 속성 기반 테스트: 개인 통계 시 비밀 거래 포함
# Feature: moneylog-backend-phase6, Property 13: 개인 통계 시 비밀 거래 포함
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pbt_personal_stats_includes_private(db_session):
    """Property 13: 개인 통계 시 비밀 거래 포함.

    *For any* 사용자와 비밀/공개 거래가 혼합된 거래 집합에 대해,
    개인 통계 조회 시 본인의 비밀 거래 금액이 집계에 포함되어야 한다.

    # Feature: moneylog-backend-phase6, Property 13: 개인 통계 시 비밀 거래 포함
    **Validates: Requirements 8.4**
    """

    # Hypothesis로 테스트 케이스 동기 생성
    cases: list[list[tuple[int, bool]]] = []

    @given(
        pairs=st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=1_000_000),
                st.booleans(),
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=30)
    def generate(pairs):
        cases.append(pairs)

    generate()

    for pairs in cases:
        # 테스트 사용자 생성
        user = await create_test_user(
            db_session,
            email=f"pbt13_{uuid.uuid4().hex[:6]}@test.com",
            nickname="PBT13",
        )

        # 거래 생성 (비밀/공개 혼합)
        for amt, is_priv in pairs:
            await _create_transaction(
                db_session,
                user.id,
                is_private=is_priv,
                actual_amount=amt,
                amount=amt,
            )
        await db_session.flush()

        # 기대값: 비밀/공개 모두 포함한 전체 합계
        expected_total = sum(amt for amt, _ in pairs)

        # 개인 통계 조회
        stats_repo = StatsRepository(db_session)
        result = await stats_repo.get_expense_sum_by_date_range(
            user.id, date(2025, 6, 1), date(2025, 6, 30)
        )

        assert result == expected_total, (
            f"개인 통계: 집계 {result} != 전체 합계 {expected_total} "
            f"(pairs={pairs})"
        )

        # 다음 케이스를 위해 롤백
        await db_session.rollback()
