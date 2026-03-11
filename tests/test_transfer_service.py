"""
TransferService 단위 테스트.

이체 생성(개인/가족), 잔액 갱신, 목록 조회(필터/정렬), 상세 조회,
권한 검증, 에러 케이스를 검증한다.
Requirements: 2.1~2.9, 3.1~3.5, 4.1~4.6
"""

import uuid
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.family_group import FamilyGroup
from app.repositories.asset_repository import AssetRepository
from app.repositories.transfer_repository import TransferRepository
from app.repositories.user_repository import UserRepository
from app.schemas.transfer import TransferCreateRequest
from app.services.transfer_service import TransferService
from tests.conftest import create_test_user


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────


async def _create_asset(
    db_session,
    user_id,
    name="테스트자산",
    balance=1_000_000,
    sort_order=1,
    family_group_id=None,
):
    """테스트용 자산을 생성한다."""
    repo = AssetRepository(db_session)
    return await repo.create({
        "user_id": user_id,
        "name": name,
        "asset_type": "BANK_ACCOUNT",
        "ownership": "PERSONAL",
        "balance": balance,
        "sort_order": sort_order,
        "family_group_id": family_group_id,
    })


async def _create_family_group(db_session, owner_id, name="테스트가족"):
    """테스트용 가족 그룹을 생성한다."""
    from datetime import datetime, timezone

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


def _build_service(db_session):
    """TransferService 인스턴스를 생성한다."""
    return TransferService(
        transfer_repo=TransferRepository(db_session),
        asset_repo=AssetRepository(db_session),
        user_repo=UserRepository(db_session),
    )


# ══════════════════════════════════════════════
# 개인 이체 생성 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_personal_transfer(db_session):
    """개인 이체 생성 정상 동작 및 잔액 갱신 검증."""
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="출금계좌", balance=500_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="입금계좌", balance=100_000, sort_order=2)

    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=from_asset.id,
        to_asset_id=to_asset.id,
        amount=200_000,
        fee=1_000,
        description="개인 이체 테스트",
        transfer_date=date(2025, 6, 1),
    )

    transfer = await service.create(user, data)

    # 이체 레코드 검증
    assert transfer.user_id == user.id
    assert transfer.from_asset_id == from_asset.id
    assert transfer.to_asset_id == to_asset.id
    assert transfer.amount == 200_000
    assert transfer.fee == 1_000
    assert transfer.description == "개인 이체 테스트"
    assert transfer.transfer_date == date(2025, 6, 1)
    assert transfer.family_group_id is None
    assert transfer.created_at is not None

    # 잔액 갱신 검증: 출금 자산 = 500000 - (200000 + 1000) = 299000
    asset_repo = AssetRepository(db_session)
    updated_from = await asset_repo.get_by_id(from_asset.id)
    assert updated_from.balance == 299_000

    # 잔액 갱신 검증: 입금 자산 = 100000 + 200000 = 300000
    updated_to = await asset_repo.get_by_id(to_asset.id)
    assert updated_to.balance == 300_000


@pytest.mark.asyncio
async def test_create_personal_transfer_with_zero_fee(db_session):
    """수수료 없는 개인 이체 생성 검증."""
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="출금계좌", balance=500_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="입금계좌", balance=100_000, sort_order=2)

    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=from_asset.id,
        to_asset_id=to_asset.id,
        amount=100_000,
        transfer_date=date(2025, 6, 1),
    )

    transfer = await service.create(user, data)

    assert transfer.fee == 0

    # 잔액 검증: 수수료 0이므로 출금 = 500000 - 100000 = 400000
    asset_repo = AssetRepository(db_session)
    updated_from = await asset_repo.get_by_id(from_asset.id)
    assert updated_from.balance == 400_000

    updated_to = await asset_repo.get_by_id(to_asset.id)
    assert updated_to.balance == 200_000


# ══════════════════════════════════════════════
# 가족 구성원 간 이체 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_family_transfer(db_session):
    """가족 구성원 간 이체 생성 및 family_group_id 설정 검증."""
    # 사용자 A (그룹장)
    user_a = await create_test_user(db_session, email="family_a@test.com", nickname="A")
    group = await _create_family_group(db_session, owner_id=user_a.id)

    # 사용자 A에 가족 그룹 설정
    user_repo = UserRepository(db_session)
    await user_repo.update(user_a.id, {"family_group_id": group.id, "role_in_group": "OWNER"})
    await db_session.refresh(user_a)

    # 사용자 B (가족 구성원)
    user_b = await create_test_user(db_session, email="family_b@test.com", nickname="B")
    await user_repo.update(user_b.id, {"family_group_id": group.id})
    await db_session.refresh(user_b)

    # 자산 생성
    from_asset = await _create_asset(db_session, user_a.id, name="A의 계좌", balance=1_000_000, sort_order=1)
    to_asset = await _create_asset(db_session, user_b.id, name="B의 계좌", balance=200_000, sort_order=1)

    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=from_asset.id,
        to_asset_id=to_asset.id,
        amount=300_000,
        fee=500,
        description="가족 이체",
        transfer_date=date(2025, 6, 15),
    )

    transfer = await service.create(user_a, data)

    # family_group_id가 설정되어야 함
    assert transfer.family_group_id == group.id
    assert transfer.user_id == user_a.id
    assert transfer.amount == 300_000

    # 잔액 갱신 검증
    asset_repo = AssetRepository(db_session)
    updated_from = await asset_repo.get_by_id(from_asset.id)
    assert updated_from.balance == 1_000_000 - (300_000 + 500)  # 699500

    updated_to = await asset_repo.get_by_id(to_asset.id)
    assert updated_to.balance == 200_000 + 300_000  # 500000


# ══════════════════════════════════════════════
# 이체 목록 조회 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_list_returns_transfers_sorted_desc(db_session):
    """이체 목록 조회 시 최신순(transfer_date DESC) 정렬 검증."""
    user = await create_test_user(db_session)
    asset_a = await _create_asset(db_session, user.id, name="계좌A", balance=5_000_000, sort_order=1)
    asset_b = await _create_asset(db_session, user.id, name="계좌B", balance=1_000_000, sort_order=2)

    service = _build_service(db_session)

    # 날짜가 다른 이체 3건 생성
    dates = [date(2025, 6, 1), date(2025, 6, 15), date(2025, 6, 10)]
    for d in dates:
        data = TransferCreateRequest(
            from_asset_id=asset_a.id,
            to_asset_id=asset_b.id,
            amount=10_000,
            transfer_date=d,
        )
        await service.create(user, data)

    result = await service.get_list(user)

    assert len(result) == 3
    # 최신순 정렬 확인
    transfer_dates = [r.transfer.transfer_date for r in result]
    assert transfer_dates == sorted(transfer_dates, reverse=True)


@pytest.mark.asyncio
async def test_get_list_with_date_filter(db_session):
    """이체 목록 조회 시 날짜 필터링 검증."""
    user = await create_test_user(db_session)
    asset_a = await _create_asset(db_session, user.id, name="계좌A", balance=5_000_000, sort_order=1)
    asset_b = await _create_asset(db_session, user.id, name="계좌B", balance=1_000_000, sort_order=2)

    service = _build_service(db_session)

    # 5월, 6월, 7월 이체 각 1건
    for d in [date(2025, 5, 15), date(2025, 6, 15), date(2025, 7, 15)]:
        data = TransferCreateRequest(
            from_asset_id=asset_a.id,
            to_asset_id=asset_b.id,
            amount=10_000,
            transfer_date=d,
        )
        await service.create(user, data)

    # 6월만 필터링
    result = await service.get_list(user, start_date=date(2025, 6, 1), end_date=date(2025, 6, 30))

    assert len(result) == 1
    assert result[0].transfer.transfer_date == date(2025, 6, 15)


@pytest.mark.asyncio
async def test_get_list_includes_asset_names(db_session):
    """이체 목록 조회 시 자산명(from_asset_name, to_asset_name) 포함 검증."""
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="신한은행", balance=1_000_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="카카오뱅크", balance=500_000, sort_order=2)

    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=from_asset.id,
        to_asset_id=to_asset.id,
        amount=50_000,
        transfer_date=date(2025, 6, 1),
    )
    await service.create(user, data)

    result = await service.get_list(user)

    assert len(result) == 1
    assert result[0].from_asset_name == "신한은행"
    assert result[0].to_asset_name == "카카오뱅크"


# ══════════════════════════════════════════════
# 이체 상세 조회 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_detail_with_asset_names(db_session):
    """이체 상세 조회 시 자산명 포함 검증."""
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="우리은행", balance=2_000_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="토스뱅크", balance=300_000, sort_order=2)

    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=from_asset.id,
        to_asset_id=to_asset.id,
        amount=100_000,
        fee=500,
        description="상세 조회 테스트",
        transfer_date=date(2025, 6, 1),
    )
    transfer = await service.create(user, data)

    detail = await service.get_detail(user, transfer.id)

    assert detail.transfer.id == transfer.id
    assert detail.from_asset_name == "우리은행"
    assert detail.to_asset_name == "토스뱅크"
    assert detail.transfer.amount == 100_000
    assert detail.transfer.fee == 500
    assert detail.transfer.description == "상세 조회 테스트"


# ══════════════════════════════════════════════
# 에러 케이스 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_same_asset_transfer_raises_validation_error():
    """동일 자산 간 이체 시 ValidationError 검증 (Pydantic 스키마 레벨)."""
    same_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="출금 자산과 입금 자산이 동일할 수 없습니다"):
        TransferCreateRequest(
            from_asset_id=same_id,
            to_asset_id=same_id,
            amount=10_000,
            transfer_date=date(2025, 6, 1),
        )


@pytest.mark.asyncio
async def test_zero_amount_raises_validation_error():
    """이체 금액 0 이하 시 ValidationError 검증 (Pydantic 스키마 레벨)."""
    with pytest.raises(ValidationError):
        TransferCreateRequest(
            from_asset_id=uuid.uuid4(),
            to_asset_id=uuid.uuid4(),
            amount=0,
            transfer_date=date(2025, 6, 1),
        )


@pytest.mark.asyncio
async def test_negative_amount_raises_validation_error():
    """이체 금액 음수 시 ValidationError 검증 (Pydantic 스키마 레벨)."""
    with pytest.raises(ValidationError):
        TransferCreateRequest(
            from_asset_id=uuid.uuid4(),
            to_asset_id=uuid.uuid4(),
            amount=-5_000,
            transfer_date=date(2025, 6, 1),
        )


@pytest.mark.asyncio
async def test_nonexistent_from_asset_raises_not_found(db_session):
    """존재하지 않는 출금 자산 이체 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    to_asset = await _create_asset(db_session, user.id, name="입금계좌", balance=100_000, sort_order=1)

    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=uuid.uuid4(),  # 존재하지 않는 자산
        to_asset_id=to_asset.id,
        amount=10_000,
        transfer_date=date(2025, 6, 1),
    )

    with pytest.raises(NotFoundError, match="자산을 찾을 수 없습니다"):
        await service.create(user, data)


@pytest.mark.asyncio
async def test_nonexistent_to_asset_raises_not_found(db_session):
    """존재하지 않는 입금 자산 이체 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="출금계좌", balance=500_000, sort_order=1)

    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=from_asset.id,
        to_asset_id=uuid.uuid4(),  # 존재하지 않는 자산
        amount=10_000,
        transfer_date=date(2025, 6, 1),
    )

    with pytest.raises(NotFoundError, match="자산을 찾을 수 없습니다"):
        await service.create(user, data)


@pytest.mark.asyncio
async def test_withdraw_from_other_user_asset_raises_forbidden(db_session):
    """본인 소유가 아닌 자산에서 출금 시 ForbiddenError 검증."""
    user_a = await create_test_user(db_session, email="owner_a@test.com", nickname="A")
    user_b = await create_test_user(db_session, email="owner_b@test.com", nickname="B")

    # A 소유 자산
    asset_a = await _create_asset(db_session, user_a.id, name="A의 계좌", balance=500_000, sort_order=1)
    # B 소유 자산
    asset_b = await _create_asset(db_session, user_b.id, name="B의 계좌", balance=300_000, sort_order=1)

    # B가 A의 자산에서 출금 시도
    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=asset_a.id,  # A 소유
        to_asset_id=asset_b.id,
        amount=10_000,
        transfer_date=date(2025, 6, 1),
    )

    with pytest.raises(ForbiddenError, match="접근 권한이 없습니다"):
        await service.create(user_b, data)


@pytest.mark.asyncio
async def test_transfer_to_different_family_group_raises_forbidden(db_session):
    """다른 가족 그룹 자산으로 이체 시 ForbiddenError 검증."""
    # 사용자 A (그룹 1)
    user_a = await create_test_user(db_session, email="group1_a@test.com", nickname="A")
    group_1 = await _create_family_group(db_session, owner_id=user_a.id, name="가족1")
    user_repo = UserRepository(db_session)
    await user_repo.update(user_a.id, {"family_group_id": group_1.id})
    await db_session.refresh(user_a)

    # 사용자 B (그룹 2)
    user_b = await create_test_user(db_session, email="group2_b@test.com", nickname="B")
    group_2 = await _create_family_group(db_session, owner_id=user_b.id, name="가족2")
    await user_repo.update(user_b.id, {"family_group_id": group_2.id})
    await db_session.refresh(user_b)

    # 자산 생성
    asset_a = await _create_asset(db_session, user_a.id, name="A의 계좌", balance=500_000, sort_order=1)
    asset_b = await _create_asset(db_session, user_b.id, name="B의 계좌", balance=300_000, sort_order=1)

    # A가 B(다른 그룹)의 자산으로 이체 시도
    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=asset_a.id,
        to_asset_id=asset_b.id,
        amount=50_000,
        transfer_date=date(2025, 6, 1),
    )

    with pytest.raises(ForbiddenError, match="접근 권한이 없습니다"):
        await service.create(user_a, data)


@pytest.mark.asyncio
async def test_get_detail_other_user_raises_forbidden(db_session):
    """다른 사용자의 이체 조회 시 ForbiddenError 검증."""
    user_a = await create_test_user(db_session, email="detail_a@test.com", nickname="A")
    user_b = await create_test_user(db_session, email="detail_b@test.com", nickname="B")

    asset_1 = await _create_asset(db_session, user_a.id, name="A계좌1", balance=1_000_000, sort_order=1)
    asset_2 = await _create_asset(db_session, user_a.id, name="A계좌2", balance=500_000, sort_order=2)

    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=asset_1.id,
        to_asset_id=asset_2.id,
        amount=50_000,
        transfer_date=date(2025, 6, 1),
    )
    transfer = await service.create(user_a, data)

    # B가 A의 이체 상세 조회 시도
    with pytest.raises(ForbiddenError, match="접근 권한이 없습니다"):
        await service.get_detail(user_b, transfer.id)


@pytest.mark.asyncio
async def test_get_detail_nonexistent_transfer_raises_not_found(db_session):
    """존재하지 않는 이체 조회 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    service = _build_service(db_session)

    with pytest.raises(NotFoundError, match="이체를 찾을 수 없습니다"):
        await service.get_detail(user, uuid.uuid4())


# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════

from hypothesis import given, settings, strategies as st


# Hypothesis 전략 정의
transfer_amounts = st.integers(min_value=1, max_value=100_000_000)
transfer_fees = st.integers(min_value=0, max_value=1_000_000)
pbt_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
descriptions = st.one_of(
    st.none(),
    st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    ),
)
balances = st.integers(min_value=0, max_value=1_000_000_000)


# ──────────────────────────────────────────────
# Property 1: 이체 생성 라운드트립
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_create_transfer_roundtrip(db_session):
    """Property 1: 유효한 이체 데이터로 create 호출 시 반환된 이체의 모든 필드가 입력과 일치한다.

    # Feature: moneylog-backend-phase6, Property 1: 이체 생성 라운드트립
    **Validates: Requirements 2.1, 2.2, 2.5**
    """

    @given(
        amount=transfer_amounts,
        fee=transfer_fees,
        transfer_date=pbt_dates,
        desc=descriptions,
        from_balance=balances,
        to_balance=balances,
    )
    @settings(max_examples=30)
    def generate(amount, fee, transfer_date, desc, from_balance, to_balance):
        cases.append((amount, fee, transfer_date, desc, from_balance, to_balance))

    cases = []
    generate()

    for amount, fee, transfer_date, desc, from_balance, to_balance in cases:
        # 각 케이스마다 독립적인 사용자/자산 생성
        user = await create_test_user(
            db_session,
            email=f"pbt1_{uuid.uuid4().hex[:8]}@test.com",
            nickname="PBT1",
        )
        from_asset = await _create_asset(
            db_session, user.id, name="출금", balance=from_balance, sort_order=1
        )
        to_asset = await _create_asset(
            db_session, user.id, name="입금", balance=to_balance, sort_order=2
        )

        service = _build_service(db_session)
        data = TransferCreateRequest(
            from_asset_id=from_asset.id,
            to_asset_id=to_asset.id,
            amount=amount,
            fee=fee,
            description=desc,
            transfer_date=transfer_date,
        )

        transfer = await service.create(user, data)

        # 모든 필드가 입력 데이터와 일치하는지 검증
        assert transfer.user_id == user.id, "user_id 불일치"
        assert transfer.from_asset_id == from_asset.id, "from_asset_id 불일치"
        assert transfer.to_asset_id == to_asset.id, "to_asset_id 불일치"
        assert transfer.amount == amount, "amount 불일치"
        assert transfer.fee == fee, "fee 불일치"
        assert transfer.description == desc, "description 불일치"
        assert transfer.transfer_date == transfer_date, "transfer_date 불일치"
        assert transfer.family_group_id is None, "개인 이체인데 family_group_id가 설정됨"
        assert transfer.created_at is not None, "created_at이 None"


# ──────────────────────────────────────────────
# Property 2: 이체 잔액 불변성
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_transfer_balance_invariant(db_session):
    """Property 2: 이체 후 from_asset.balance = B_from - (amount + fee), to_asset.balance = B_to + amount.

    # Feature: moneylog-backend-phase6, Property 2: 이체 잔액 불변성
    **Validates: Requirements 2.3, 2.4, 3.3**
    """

    @given(
        amount=transfer_amounts,
        fee=transfer_fees,
        transfer_date=pbt_dates,
        from_balance=balances,
        to_balance=balances,
    )
    @settings(max_examples=30)
    def generate(amount, fee, transfer_date, from_balance, to_balance):
        cases.append((amount, fee, transfer_date, from_balance, to_balance))

    cases = []
    generate()

    asset_repo = AssetRepository(db_session)

    for amount, fee, transfer_date, from_balance, to_balance in cases:
        user = await create_test_user(
            db_session,
            email=f"pbt2_{uuid.uuid4().hex[:8]}@test.com",
            nickname="PBT2",
        )
        from_asset = await _create_asset(
            db_session, user.id, name="출금", balance=from_balance, sort_order=1
        )
        to_asset = await _create_asset(
            db_session, user.id, name="입금", balance=to_balance, sort_order=2
        )

        service = _build_service(db_session)
        data = TransferCreateRequest(
            from_asset_id=from_asset.id,
            to_asset_id=to_asset.id,
            amount=amount,
            fee=fee,
            transfer_date=transfer_date,
        )

        await service.create(user, data)

        # 잔액 불변성 검증
        updated_from = await asset_repo.get_by_id(from_asset.id)
        updated_to = await asset_repo.get_by_id(to_asset.id)

        expected_from_balance = from_balance - (amount + fee)
        expected_to_balance = to_balance + amount

        assert updated_from.balance == expected_from_balance, (
            f"출금 잔액 불일치: {updated_from.balance} != {expected_from_balance}"
        )
        assert updated_to.balance == expected_to_balance, (
            f"입금 잔액 불일치: {updated_to.balance} != {expected_to_balance}"
        )


# ──────────────────────────────────────────────
# Property 3: 이체 입력 검증 (순수 검증, DB 불필요)
# ──────────────────────────────────────────────


@given(
    asset_id=st.uuids(),
    amount=st.integers(min_value=1, max_value=100_000_000),
    transfer_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
)
@settings(max_examples=30)
def test_pbt_same_asset_raises_validation_error(asset_id, amount, transfer_date):
    """Property 3a: from_asset_id == to_asset_id이면 ValidationError가 발생해야 한다.

    # Feature: moneylog-backend-phase6, Property 3: 이체 입력 검증
    **Validates: Requirements 2.6, 2.9**
    """
    with pytest.raises(ValidationError, match="출금 자산과 입금 자산이 동일할 수 없습니다"):
        TransferCreateRequest(
            from_asset_id=asset_id,
            to_asset_id=asset_id,
            amount=amount,
            transfer_date=transfer_date,
        )


@given(
    from_id=st.uuids(),
    to_id=st.uuids(),
    amount=st.integers(min_value=-100_000_000, max_value=0),
    transfer_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
)
@settings(max_examples=30)
def test_pbt_non_positive_amount_raises_validation_error(from_id, to_id, amount, transfer_date):
    """Property 3b: amount ≤ 0이면 ValidationError가 발생해야 한다.

    # Feature: moneylog-backend-phase6, Property 3: 이체 입력 검증
    **Validates: Requirements 2.6, 2.9**
    """
    # from_id == to_id인 경우 다른 검증이 먼저 발생할 수 있으므로 다른 UUID 보장
    if from_id == to_id:
        return  # 동일 자산 검증은 Property 3a에서 처리
    with pytest.raises(ValidationError):
        TransferCreateRequest(
            from_asset_id=from_id,
            to_asset_id=to_id,
            amount=amount,
            transfer_date=transfer_date,
        )


# ──────────────────────────────────────────────
# Property 4: 존재하지 않는 리소스 접근 시 NotFoundError
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_nonexistent_resource_raises_not_found(db_session):
    """Property 4: 존재하지 않는 자산/이체 접근 시 NotFoundError가 발생해야 한다.

    # Feature: moneylog-backend-phase6, Property 4: 존재하지 않는 리소스 접근 시 NotFoundError
    **Validates: Requirements 2.7, 4.6**
    """

    @given(fake_uuid=st.uuids())
    @settings(max_examples=30)
    def generate(fake_uuid):
        cases.append(fake_uuid)

    cases = []
    generate()

    user = await create_test_user(
        db_session,
        email=f"pbt4_{uuid.uuid4().hex[:8]}@test.com",
        nickname="PBT4",
    )
    # 유효한 자산 하나 생성 (to_asset용)
    valid_asset = await _create_asset(
        db_session, user.id, name="유효자산", balance=1_000_000, sort_order=1
    )

    service = _build_service(db_session)

    for fake_id in cases:
        # 4a: 존재하지 않는 from_asset으로 이체 생성 시 NotFoundError
        data = TransferCreateRequest(
            from_asset_id=fake_id,
            to_asset_id=valid_asset.id,
            amount=10_000,
            transfer_date=date(2025, 6, 1),
        )
        with pytest.raises(NotFoundError):
            await service.create(user, data)

        # 4b: 존재하지 않는 이체 조회 시 NotFoundError
        with pytest.raises(NotFoundError):
            await service.get_detail(user, fake_id)


# ──────────────────────────────────────────────
# Property 5: 이체 접근 권한 검증
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_access_control_forbidden(db_session):
    """Property 5: 다른 사용자의 자산/이체 접근 시 ForbiddenError가 발생해야 한다.

    # Feature: moneylog-backend-phase6, Property 5: 이체 접근 권한 검증
    **Validates: Requirements 2.8, 3.4, 3.5, 4.5**
    """

    @given(
        amount=transfer_amounts,
        fee=transfer_fees,
        transfer_date=pbt_dates,
    )
    @settings(max_examples=30)
    def generate(amount, fee, transfer_date):
        cases.append((amount, fee, transfer_date))

    cases = []
    generate()

    for amount, fee, transfer_date in cases:
        # 사용자 A, B 생성 (가족 그룹 없음)
        user_a = await create_test_user(
            db_session,
            email=f"pbt5a_{uuid.uuid4().hex[:8]}@test.com",
            nickname="A",
        )
        user_b = await create_test_user(
            db_session,
            email=f"pbt5b_{uuid.uuid4().hex[:8]}@test.com",
            nickname="B",
        )

        # A 소유 자산
        asset_a = await _create_asset(
            db_session, user_a.id, name="A자산", balance=1_000_000_000, sort_order=1
        )
        # B 소유 자산
        asset_b = await _create_asset(
            db_session, user_b.id, name="B자산", balance=1_000_000_000, sort_order=1
        )

        service = _build_service(db_session)

        # 5a: B가 A의 자산에서 출금 시도 → ForbiddenError
        data = TransferCreateRequest(
            from_asset_id=asset_a.id,
            to_asset_id=asset_b.id,
            amount=amount,
            fee=fee,
            transfer_date=transfer_date,
        )
        with pytest.raises(ForbiddenError):
            await service.create(user_b, data)

        # A가 자기 자산 간 이체 생성 (B의 이체 조회 테스트용)
        asset_a2 = await _create_asset(
            db_session, user_a.id, name="A자산2", balance=1_000_000_000, sort_order=2
        )
        data_a = TransferCreateRequest(
            from_asset_id=asset_a.id,
            to_asset_id=asset_a2.id,
            amount=amount,
            fee=fee,
            transfer_date=transfer_date,
        )
        transfer_a = await service.create(user_a, data_a)

        # 5b: B가 A의 이체 상세 조회 시도 → ForbiddenError
        with pytest.raises(ForbiddenError):
            await service.get_detail(user_b, transfer_a.id)


# ──────────────────────────────────────────────
# Property 6: 가족 이체 그룹 설정
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_family_transfer_group_id(db_session):
    """Property 6: 가족 이체 시 family_group_id가 해당 가족 그룹 ID와 일치해야 한다.

    # Feature: moneylog-backend-phase6, Property 6: 가족 이체 그룹 설정
    **Validates: Requirements 3.1, 3.2**
    """

    @given(
        amount=transfer_amounts,
        fee=transfer_fees,
        transfer_date=pbt_dates,
    )
    @settings(max_examples=30)
    def generate(amount, fee, transfer_date):
        cases.append((amount, fee, transfer_date))

    cases = []
    generate()

    user_repo = UserRepository(db_session)

    for amount, fee, transfer_date in cases:
        # 가족 그룹 생성
        user_a = await create_test_user(
            db_session,
            email=f"pbt6a_{uuid.uuid4().hex[:8]}@test.com",
            nickname="A",
        )
        group = await _create_family_group(db_session, owner_id=user_a.id)
        await user_repo.update(user_a.id, {"family_group_id": group.id, "role_in_group": "OWNER"})
        await db_session.refresh(user_a)

        user_b = await create_test_user(
            db_session,
            email=f"pbt6b_{uuid.uuid4().hex[:8]}@test.com",
            nickname="B",
        )
        await user_repo.update(user_b.id, {"family_group_id": group.id})
        await db_session.refresh(user_b)

        # 자산 생성
        from_asset = await _create_asset(
            db_session, user_a.id, name="A계좌", balance=1_000_000_000, sort_order=1
        )
        to_asset = await _create_asset(
            db_session, user_b.id, name="B계좌", balance=0, sort_order=1
        )

        service = _build_service(db_session)
        data = TransferCreateRequest(
            from_asset_id=from_asset.id,
            to_asset_id=to_asset.id,
            amount=amount,
            fee=fee,
            transfer_date=transfer_date,
        )

        transfer = await service.create(user_a, data)

        # family_group_id가 가족 그룹 ID와 일치해야 함
        assert transfer.family_group_id == group.id, (
            f"family_group_id 불일치: {transfer.family_group_id} != {group.id}"
        )


# ──────────────────────────────────────────────
# Property 7: 이체 목록 필터링 및 정렬
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_list_filtering_and_sorting(db_session):
    """Property 7: get_list는 transfer_date DESC 정렬, 날짜 필터가 올바르게 동작해야 한다.

    # Feature: moneylog-backend-phase6, Property 7: 이체 목록 필터링 및 정렬
    **Validates: Requirements 4.1, 4.2**
    """

    @given(
        dates_list=st.lists(
            st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            min_size=2,
            max_size=10,
        ),
        filter_start=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
        filter_end=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    )
    @settings(max_examples=30)
    def generate(dates_list, filter_start, filter_end):
        # filter_start <= filter_end 보장
        if filter_start > filter_end:
            filter_start, filter_end = filter_end, filter_start
        cases.append((dates_list, filter_start, filter_end))

    cases = []
    generate()

    for dates_list, filter_start, filter_end in cases:
        user = await create_test_user(
            db_session,
            email=f"pbt7_{uuid.uuid4().hex[:8]}@test.com",
            nickname="PBT7",
        )
        asset_a = await _create_asset(
            db_session, user.id, name="계좌A", balance=1_000_000_000, sort_order=1
        )
        asset_b = await _create_asset(
            db_session, user.id, name="계좌B", balance=0, sort_order=2
        )

        service = _build_service(db_session)

        # 다양한 날짜로 이체 생성
        for d in dates_list:
            data = TransferCreateRequest(
                from_asset_id=asset_a.id,
                to_asset_id=asset_b.id,
                amount=1_000,
                transfer_date=d,
            )
            await service.create(user, data)

        # 7a: 전체 목록 조회 시 transfer_date DESC 정렬 검증
        all_result = await service.get_list(user)
        all_dates = [r.transfer.transfer_date for r in all_result]
        assert all_dates == sorted(all_dates, reverse=True), "전체 목록이 내림차순이 아님"

        # 7b: 날짜 필터 적용 시 범위 내 데이터만 반환
        filtered = await service.get_list(user, start_date=filter_start, end_date=filter_end)
        for item in filtered:
            td = item.transfer.transfer_date
            assert filter_start <= td <= filter_end, (
                f"필터 범위 밖 데이터: {td} not in [{filter_start}, {filter_end}]"
            )


# ──────────────────────────────────────────────
# Property 8: 이체 상세 조회 자산명 포함
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pbt_detail_includes_asset_names(db_session):
    """Property 8: get_detail 시 from_asset_name, to_asset_name이 실제 자산명과 일치해야 한다.

    # Feature: moneylog-backend-phase6, Property 8: 이체 상세 조회 자산명 포함
    **Validates: Requirements 4.3, 4.4**
    """

    @given(
        amount=transfer_amounts,
        fee=transfer_fees,
        transfer_date=pbt_dates,
        from_name=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
        to_name=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
    )
    @settings(max_examples=30)
    def generate(amount, fee, transfer_date, from_name, to_name):
        cases.append((amount, fee, transfer_date, from_name, to_name))

    cases = []
    generate()

    for amount, fee, transfer_date, from_name, to_name in cases:
        user = await create_test_user(
            db_session,
            email=f"pbt8_{uuid.uuid4().hex[:8]}@test.com",
            nickname="PBT8",
        )
        from_asset = await _create_asset(
            db_session, user.id, name=from_name, balance=1_000_000_000, sort_order=1
        )
        to_asset = await _create_asset(
            db_session, user.id, name=to_name, balance=0, sort_order=2
        )

        service = _build_service(db_session)
        data = TransferCreateRequest(
            from_asset_id=from_asset.id,
            to_asset_id=to_asset.id,
            amount=amount,
            fee=fee,
            transfer_date=transfer_date,
        )
        transfer = await service.create(user, data)

        detail = await service.get_detail(user, transfer.id)

        # 자산명이 실제 자산의 이름과 일치해야 함
        assert detail.from_asset_name == from_name, (
            f"from_asset_name 불일치: '{detail.from_asset_name}' != '{from_name}'"
        )
        assert detail.to_asset_name == to_name, (
            f"to_asset_name 불일치: '{detail.to_asset_name}' != '{to_name}'"
        )
