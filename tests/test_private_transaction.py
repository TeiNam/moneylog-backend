"""
비밀 모드(is_private) 단위 테스트 및 속성 기반 테스트.

비밀 거래 생성/수정, 가족 그룹 조회 시 비밀 거래 제외,
본인 조회 시 비밀 거래 포함, 다른 구성원 비밀 거래 직접 조회 차단을 검증한다.
Requirements: 6.1, 6.2, 6.3, 7.1, 7.2, 7.3
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from hypothesis import given, settings, strategies as st

from app.core.exceptions import ForbiddenError
from app.models.family_group import FamilyGroup
from app.repositories.ceremony_person_repository import CeremonyPersonRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.transaction import (
    TransactionCreateRequest,
    TransactionFilterParams,
    TransactionUpdateRequest,
)
from app.services.transaction_service import TransactionService
from tests.conftest import create_test_user


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────


def _build_service(db_session) -> TransactionService:
    """TransactionService 인스턴스를 생성한다."""
    return TransactionService(
        transaction_repo=TransactionRepository(db_session),
        ceremony_person_repo=CeremonyPersonRepository(db_session),
    )


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
        email=f"family_a_{uuid.uuid4().hex[:6]}@test.com",
        nickname="A",
    )
    user_b = await create_test_user(
        db_session,
        email=f"family_b_{uuid.uuid4().hex[:6]}@test.com",
        nickname="B",
    )
    group = await _create_family_group(db_session, owner_id=user_a.id)

    user_repo = UserRepository(db_session)
    await user_repo.update(user_a.id, {"family_group_id": group.id, "role_in_group": "OWNER"})
    await user_repo.update(user_b.id, {"family_group_id": group.id})
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    return user_a, user_b, group


def _make_create_request(is_private: bool = False, **overrides) -> TransactionCreateRequest:
    """기본 거래 생성 요청을 만든다."""
    defaults = {
        "date": date(2025, 6, 1),
        "area": "GENERAL",
        "type": "EXPENSE",
        "major_category": "식비",
        "minor_category": "외식",
        "description": "테스트 거래",
        "amount": 10_000,
        "source": "MANUAL",
        "is_private": is_private,
    }
    defaults.update(overrides)
    return TransactionCreateRequest(**defaults)


# ══════════════════════════════════════════════
# 단위 테스트: 비밀 거래 생성
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_private_transaction(db_session):
    """비밀 거래 생성 (is_private=true) 검증. (Req 6.1)"""
    user = await create_test_user(db_session)
    service = _build_service(db_session)

    data = _make_create_request(is_private=True)
    tx = await service.create(user, data)

    assert tx.is_private is True
    assert tx.user_id == user.id


@pytest.mark.asyncio
async def test_create_transaction_default_not_private(db_session):
    """is_private 미제공 시 기본값 false 검증. (Req 6.2)"""
    user = await create_test_user(db_session)
    service = _build_service(db_session)

    # is_private를 명시하지 않음
    data = TransactionCreateRequest(
        date=date(2025, 6, 1),
        area="GENERAL",
        type="EXPENSE",
        major_category="식비",
        amount=5_000,
        source="MANUAL",
    )
    tx = await service.create(user, data)

    assert tx.is_private is False


@pytest.mark.asyncio
async def test_update_is_private(db_session):
    """거래 수정으로 is_private 변경 검증. (Req 6.3)"""
    user = await create_test_user(db_session)
    service = _build_service(db_session)

    # 공개 거래 생성
    data = _make_create_request(is_private=False)
    tx = await service.create(user, data)
    assert tx.is_private is False

    # 비밀로 변경
    updated = await service.update(user, tx.id, TransactionUpdateRequest(is_private=True))
    assert updated.is_private is True

    # 다시 공개로 변경
    updated2 = await service.update(user, tx.id, TransactionUpdateRequest(is_private=False))
    assert updated2.is_private is False


# ══════════════════════════════════════════════
# 단위 테스트: 가족 그룹 조회 시 비밀 거래 제외
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_family_list_excludes_other_member_private(db_session):
    """가족 그룹 조회 시 다른 구성원 비밀 거래 제외 검증. (Req 7.1)"""
    user_a, user_b, group = await _setup_family(db_session)
    service = _build_service(db_session)

    # A가 공개 거래 1건, 비밀 거래 1건 생성
    await service.create(user_a, _make_create_request(is_private=False, description="A공개"))
    await service.create(user_a, _make_create_request(is_private=True, description="A비밀"))

    # B가 가족 그룹 조회 → A의 비밀 거래는 제외되어야 함
    filters = TransactionFilterParams(family_group=True)
    transactions, total = await service.get_list(user_b, filters)

    descriptions = [t.description for t in transactions]
    assert "A공개" in descriptions
    assert "A비밀" not in descriptions


@pytest.mark.asyncio
async def test_own_list_includes_private(db_session):
    """본인 조회 시 비밀 거래 포함 검증. (Req 7.2)"""
    user_a, user_b, group = await _setup_family(db_session)
    service = _build_service(db_session)

    # A가 비밀 거래 생성
    await service.create(user_a, _make_create_request(is_private=True, description="A비밀"))
    await service.create(user_a, _make_create_request(is_private=False, description="A공개"))

    # A가 가족 그룹 조회 → 본인 비밀 거래 포함
    filters = TransactionFilterParams(family_group=True)
    transactions, total = await service.get_list(user_a, filters)

    descriptions = [t.description for t in transactions]
    assert "A비밀" in descriptions
    assert "A공개" in descriptions


# ══════════════════════════════════════════════
# 단위 테스트: 비밀 거래 직접 조회 차단
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_other_member_direct_access_private_forbidden(db_session):
    """다른 구성원 비밀 거래 직접 조회 시 ForbiddenError 검증. (Req 7.3)"""
    user_a, user_b, group = await _setup_family(db_session)
    service = _build_service(db_session)

    # A가 비밀 거래 생성
    tx = await service.create(user_a, _make_create_request(is_private=True))

    # B가 A의 비밀 거래 직접 조회 시도
    with pytest.raises(ForbiddenError, match="해당 거래에 대한 접근 권한이 없습니다"):
        await service.get_detail(user_b, tx.id)


@pytest.mark.asyncio
async def test_other_member_direct_access_public_allowed(db_session):
    """다른 구성원의 공개 거래 직접 조회는 허용 검증."""
    user_a, user_b, group = await _setup_family(db_session)
    service = _build_service(db_session)

    # A가 공개 거래 생성
    tx = await service.create(user_a, _make_create_request(is_private=False))

    # B가 A의 공개 거래 직접 조회 → 허용
    detail = await service.get_detail(user_b, tx.id)
    assert detail.transaction.id == tx.id


# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════

# Hypothesis 전략 정의
pbt_amounts = st.integers(min_value=1, max_value=10_000_000)
pbt_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
pbt_is_private = st.booleans()


# ──────────────────────────────────────────────
# Property 9: 비밀 모드 생성 라운드트립
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_private_mode_roundtrip(db_session):
    """Property 9: is_private=true → true, 미제공 → false, 수정 시 반영.

    # Feature: moneylog-backend-phase6, Property 9: 비밀 모드 생성 라운드트립
    **Validates: Requirements 6.1, 6.2, 6.3**
    """

    @given(
        is_private=pbt_is_private,
        amount=pbt_amounts,
        tx_date=pbt_dates,
    )
    @settings(max_examples=30)
    def generate(is_private, amount, tx_date):
        cases.append((is_private, amount, tx_date))

    cases = []
    generate()

    service = _build_service(db_session)

    for is_private, amount, tx_date in cases:
        user = await create_test_user(
            db_session,
            email=f"pbt9_{uuid.uuid4().hex[:8]}@test.com",
            nickname="PBT9",
        )

        # 1) is_private 값으로 생성 시 해당 값이 반영되어야 함
        data = _make_create_request(is_private=is_private, amount=amount, date=tx_date)
        tx = await service.create(user, data)
        assert tx.is_private == is_private, (
            f"생성 시 is_private 불일치: {tx.is_private} != {is_private}"
        )

        # 2) 반대 값으로 수정 시 반영되어야 함
        toggled = not is_private
        updated = await service.update(user, tx.id, TransactionUpdateRequest(is_private=toggled))
        assert updated.is_private == toggled, (
            f"수정 시 is_private 불일치: {updated.is_private} != {toggled}"
        )

    # 3) is_private 미제공 시 기본값 false 검증
    default_user = await create_test_user(
        db_session,
        email=f"pbt9_default_{uuid.uuid4().hex[:8]}@test.com",
        nickname="PBT9D",
    )
    default_data = TransactionCreateRequest(
        date=date(2025, 1, 1),
        area="GENERAL",
        type="EXPENSE",
        major_category="기타",
        amount=1000,
        source="MANUAL",
    )
    default_tx = await service.create(default_user, default_data)
    assert default_tx.is_private is False, "미제공 시 기본값이 false가 아님"


# ──────────────────────────────────────────────
# Property 10: 비밀 거래 가시성
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_private_transaction_visibility(db_session):
    """Property 10: 가족 조회 시 다른 구성원 비밀 거래 제외, 본인 조회 시 포함.

    # Feature: moneylog-backend-phase6, Property 10: 비밀 거래 가시성
    **Validates: Requirements 7.1, 7.2**
    """

    @given(
        num_private=st.integers(min_value=1, max_value=5),
        num_public=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=30)
    def generate(num_private, num_public):
        cases.append((num_private, num_public))

    cases = []
    generate()

    for num_private, num_public in cases:
        user_a, user_b, group = await _setup_family(db_session)
        service = _build_service(db_session)

        # A가 비밀 거래 num_private건, 공개 거래 num_public건 생성
        for i in range(num_private):
            await service.create(
                user_a,
                _make_create_request(
                    is_private=True,
                    description=f"A비밀{i}",
                    amount=1000 + i,
                ),
            )
        for i in range(num_public):
            await service.create(
                user_a,
                _make_create_request(
                    is_private=False,
                    description=f"A공개{i}",
                    amount=2000 + i,
                ),
            )

        # B가 가족 그룹 조회 → A의 비밀 거래 제외
        b_txs, _ = await service.get_list(user_b, TransactionFilterParams(family_group=True))
        b_private_count = sum(1 for t in b_txs if t.is_private and t.user_id == user_a.id)
        assert b_private_count == 0, (
            f"B의 가족 조회에 A의 비밀 거래가 {b_private_count}건 포함됨"
        )

        # A가 가족 그룹 조회 → 본인 비밀 거래 포함
        a_txs, _ = await service.get_list(user_a, TransactionFilterParams(family_group=True))
        a_private_count = sum(1 for t in a_txs if t.is_private and t.user_id == user_a.id)
        assert a_private_count == num_private, (
            f"A의 가족 조회에 본인 비밀 거래 {a_private_count}건 (기대: {num_private}건)"
        )

        # A의 공개 거래는 B에게도 보여야 함
        b_public_from_a = sum(
            1 for t in b_txs if not t.is_private and t.user_id == user_a.id
        )
        assert b_public_from_a == num_public, (
            f"B에게 보이는 A의 공개 거래 {b_public_from_a}건 (기대: {num_public}건)"
        )


# ──────────────────────────────────────────────
# Property 11: 비밀 거래 직접 조회 차단
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_private_transaction_direct_access_blocked(db_session):
    """Property 11: 다른 구성원의 비밀 거래 직접 조회 시 ForbiddenError.

    # Feature: moneylog-backend-phase6, Property 11: 비밀 거래 직접 조회 차단
    **Validates: Requirements 7.3**
    """

    @given(
        amount=pbt_amounts,
        tx_date=pbt_dates,
    )
    @settings(max_examples=30)
    def generate(amount, tx_date):
        cases.append((amount, tx_date))

    cases = []
    generate()

    for amount, tx_date in cases:
        user_a, user_b, group = await _setup_family(db_session)
        service = _build_service(db_session)

        # A가 비밀 거래 생성
        tx = await service.create(
            user_a,
            _make_create_request(is_private=True, amount=amount, date=tx_date),
        )

        # B가 A의 비밀 거래 직접 조회 → ForbiddenError
        with pytest.raises(ForbiddenError):
            await service.get_detail(user_b, tx.id)

        # A 본인은 조회 가능
        detail = await service.get_detail(user_a, tx.id)
        assert detail.transaction.id == tx.id
        assert detail.transaction.is_private is True
