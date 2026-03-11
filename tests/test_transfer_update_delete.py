"""
이체(Transfer) 수정/삭제 단위 테스트.

TransferService의 update, delete 메서드를 직접 테스트한다.
잔액 재조정/원복, 권한 검증, 에러 케이스를 검증한다.
Requirements: 12.1~12.7
"""

import uuid
from datetime import date

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.repositories.asset_repository import AssetRepository
from app.repositories.transfer_repository import TransferRepository
from app.repositories.user_repository import UserRepository
from app.schemas.transfer import TransferCreateRequest, TransferUpdateRequest
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
    })


def _build_service(db_session):
    """TransferService 인스턴스를 생성한다."""
    return TransferService(
        transfer_repo=TransferRepository(db_session),
        asset_repo=AssetRepository(db_session),
        user_repo=UserRepository(db_session),
    )


async def _create_transfer(db_session, user, from_asset, to_asset, amount=200_000, fee=1_000):
    """테스트용 이체를 생성하고 반환한다."""
    service = _build_service(db_session)
    data = TransferCreateRequest(
        from_asset_id=from_asset.id,
        to_asset_id=to_asset.id,
        amount=amount,
        fee=fee,
        description="테스트 이체",
        transfer_date=date(2025, 6, 1),
    )
    return await service.create(user, data)


# ══════════════════════════════════════════════
# 이체 수정 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_transfer_amount_and_balance_readjust(db_session):
    """이체 수정 시 금액 변경 및 잔액 재조정 검증.

    초기: from=500,000 / to=100,000
    이체 생성: amount=200,000, fee=1,000
      → from=299,000 / to=300,000
    이체 수정: amount=150,000 (fee 유지)
      → 원복: from=299,000+200,000+1,000=500,000 / to=300,000-200,000=100,000
      → 재계산: from=500,000-150,000-1,000=349,000 / to=100,000+150,000=250,000
    """
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="출금계좌", balance=500_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="입금계좌", balance=100_000, sort_order=2)

    transfer = await _create_transfer(db_session, user, from_asset, to_asset, amount=200_000, fee=1_000)

    # 이체 수정: 금액만 변경
    service = _build_service(db_session)
    update_data = TransferUpdateRequest(amount=150_000)
    updated = await service.update(user, transfer.id, update_data)

    # 수정된 이체 레코드 검증
    assert updated.amount == 150_000
    assert updated.fee == 1_000  # fee는 변경하지 않았으므로 유지

    # 잔액 재조정 검증
    asset_repo = AssetRepository(db_session)
    updated_from = await asset_repo.get_by_id(from_asset.id)
    updated_to = await asset_repo.get_by_id(to_asset.id)

    assert updated_from.balance == 349_000  # 500,000 - (150,000 + 1,000)
    assert updated_to.balance == 250_000    # 100,000 + 150,000


@pytest.mark.asyncio
async def test_update_transfer_fee_and_balance_readjust(db_session):
    """이체 수정 시 수수료 변경 및 잔액 재조정 검증.

    초기: from=500,000 / to=100,000
    이체 생성: amount=200,000, fee=1,000
      → from=299,000 / to=300,000
    이체 수정: fee=5,000 (amount 유지)
      → 원복 후 재계산: from=500,000-200,000-5,000=295,000 / to=100,000+200,000=300,000
    """
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="출금계좌", balance=500_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="입금계좌", balance=100_000, sort_order=2)

    transfer = await _create_transfer(db_session, user, from_asset, to_asset, amount=200_000, fee=1_000)

    # 이체 수정: 수수료만 변경
    service = _build_service(db_session)
    update_data = TransferUpdateRequest(fee=5_000)
    updated = await service.update(user, transfer.id, update_data)

    assert updated.fee == 5_000
    assert updated.amount == 200_000  # amount는 유지

    # 잔액 검증
    asset_repo = AssetRepository(db_session)
    updated_from = await asset_repo.get_by_id(from_asset.id)
    updated_to = await asset_repo.get_by_id(to_asset.id)

    assert updated_from.balance == 295_000  # 500,000 - (200,000 + 5,000)
    assert updated_to.balance == 300_000    # 100,000 + 200,000 (입금 자산은 fee 영향 없음)


@pytest.mark.asyncio
async def test_update_transfer_description_and_date(db_session):
    """이체 수정 시 설명/날짜 변경 검증 (잔액 변동 없음)."""
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="출금계좌", balance=500_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="입금계좌", balance=100_000, sort_order=2)

    transfer = await _create_transfer(db_session, user, from_asset, to_asset, amount=200_000, fee=1_000)

    # 이체 수정: 설명과 날짜만 변경
    service = _build_service(db_session)
    update_data = TransferUpdateRequest(description="수정된 설명", transfer_date=date(2025, 7, 15))
    updated = await service.update(user, transfer.id, update_data)

    assert updated.description == "수정된 설명"
    assert updated.transfer_date == date(2025, 7, 15)
    assert updated.amount == 200_000  # 금액 유지
    assert updated.fee == 1_000       # 수수료 유지

    # 잔액 변동 없음 검증 (금액/수수료 미변경)
    asset_repo = AssetRepository(db_session)
    updated_from = await asset_repo.get_by_id(from_asset.id)
    updated_to = await asset_repo.get_by_id(to_asset.id)

    assert updated_from.balance == 299_000  # 이체 생성 후 잔액 그대로
    assert updated_to.balance == 300_000


# ══════════════════════════════════════════════
# 이체 삭제 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_delete_transfer_and_balance_restore(db_session):
    """이체 삭제 시 잔액 원복 검증.

    초기: from=500,000 / to=100,000
    이체 생성: amount=200,000, fee=1,000
      → from=299,000 / to=300,000
    이체 삭제:
      → from=299,000+200,000+1,000=500,000 / to=300,000-200,000=100,000
    """
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="출금계좌", balance=500_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="입금계좌", balance=100_000, sort_order=2)

    transfer = await _create_transfer(db_session, user, from_asset, to_asset, amount=200_000, fee=1_000)

    # 이체 삭제
    service = _build_service(db_session)
    await service.delete(user, transfer.id)

    # 잔액 원복 검증
    asset_repo = AssetRepository(db_session)
    restored_from = await asset_repo.get_by_id(from_asset.id)
    restored_to = await asset_repo.get_by_id(to_asset.id)

    assert restored_from.balance == 500_000  # 원래 잔액으로 복원
    assert restored_to.balance == 100_000    # 원래 잔액으로 복원

    # 이체 레코드 삭제 확인
    transfer_repo = TransferRepository(db_session)
    deleted = await transfer_repo.get_by_id(transfer.id)
    assert deleted is None


@pytest.mark.asyncio
async def test_delete_transfer_with_zero_fee(db_session):
    """수수료 0인 이체 삭제 시 잔액 원복 검증."""
    user = await create_test_user(db_session)
    from_asset = await _create_asset(db_session, user.id, name="출금계좌", balance=300_000, sort_order=1)
    to_asset = await _create_asset(db_session, user.id, name="입금계좌", balance=50_000, sort_order=2)

    transfer = await _create_transfer(db_session, user, from_asset, to_asset, amount=100_000, fee=0)

    service = _build_service(db_session)
    await service.delete(user, transfer.id)

    asset_repo = AssetRepository(db_session)
    restored_from = await asset_repo.get_by_id(from_asset.id)
    restored_to = await asset_repo.get_by_id(to_asset.id)

    assert restored_from.balance == 300_000
    assert restored_to.balance == 50_000


# ══════════════════════════════════════════════
# 권한 검증 테스트 — ForbiddenError
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_other_user_transfer_raises_forbidden(db_session):
    """다른 사용자의 이체 수정 시 ForbiddenError 검증."""
    user_a = await create_test_user(db_session, email="owner_a@test.com", nickname="A")
    user_b = await create_test_user(db_session, email="owner_b@test.com", nickname="B")

    from_asset = await _create_asset(db_session, user_a.id, name="A출금", balance=500_000, sort_order=1)
    to_asset = await _create_asset(db_session, user_a.id, name="A입금", balance=100_000, sort_order=2)

    # A가 이체 생성
    transfer = await _create_transfer(db_session, user_a, from_asset, to_asset)

    # B가 A의 이체 수정 시도
    service = _build_service(db_session)
    update_data = TransferUpdateRequest(amount=50_000)

    with pytest.raises(ForbiddenError, match="접근 권한이 없습니다"):
        await service.update(user_b, transfer.id, update_data)


@pytest.mark.asyncio
async def test_delete_other_user_transfer_raises_forbidden(db_session):
    """다른 사용자의 이체 삭제 시 ForbiddenError 검증."""
    user_a = await create_test_user(db_session, email="del_a@test.com", nickname="A")
    user_b = await create_test_user(db_session, email="del_b@test.com", nickname="B")

    from_asset = await _create_asset(db_session, user_a.id, name="A출금", balance=500_000, sort_order=1)
    to_asset = await _create_asset(db_session, user_a.id, name="A입금", balance=100_000, sort_order=2)

    # A가 이체 생성
    transfer = await _create_transfer(db_session, user_a, from_asset, to_asset)

    # B가 A의 이체 삭제 시도
    service = _build_service(db_session)

    with pytest.raises(ForbiddenError, match="접근 권한이 없습니다"):
        await service.delete(user_b, transfer.id)


# ══════════════════════════════════════════════
# 존재하지 않는 이체 — NotFoundError
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_nonexistent_transfer_raises_not_found(db_session):
    """존재하지 않는 이체 수정 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    service = _build_service(db_session)
    update_data = TransferUpdateRequest(amount=50_000)

    with pytest.raises(NotFoundError, match="이체를 찾을 수 없습니다"):
        await service.update(user, uuid.uuid4(), update_data)


@pytest.mark.asyncio
async def test_delete_nonexistent_transfer_raises_not_found(db_session):
    """존재하지 않는 이체 삭제 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    service = _build_service(db_session)

    with pytest.raises(NotFoundError, match="이체를 찾을 수 없습니다"):
        await service.delete(user, uuid.uuid4())
