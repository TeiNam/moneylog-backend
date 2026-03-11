"""
비밀번호 변경 단위 테스트.

EmailAuthService.change_password 메서드의 정상 동작,
현재 비밀번호 불일치, 새 비밀번호 규칙 미충족 케이스를 검증한다.

요구사항: 8.1, 8.3, 8.4
"""

import pytest

from app.core.exceptions import BadRequestError
from app.core.security import verify_password
from app.repositories.user_repository import UserRepository
from app.services.auth_service import EmailAuthService
from tests.conftest import create_test_user


# ══════════════════════════════════════════════
# 비밀번호 변경 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_change_password_success(db_session):
    """정상적인 비밀번호 변경 검증. (요구사항 8.1)"""
    user = await create_test_user(
        db_session, email="pw@test.com", password="oldPass1", nickname="PW"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    await service.change_password(user, "oldPass1", "newPass1")

    # DB에서 사용자를 다시 조회하여 새 비밀번호로 검증
    updated_user = await repo.get_by_id(user.id)
    assert updated_user is not None
    assert verify_password("newPass1", updated_user.password_hash)
    # 이전 비밀번호는 더 이상 일치하지 않아야 함
    assert not verify_password("oldPass1", updated_user.password_hash)


@pytest.mark.asyncio
async def test_change_password_wrong_current(db_session):
    """현재 비밀번호 불일치 시 BadRequestError 검증. (요구사항 8.3)"""
    user = await create_test_user(
        db_session, email="pw2@test.com", password="oldPass1", nickname="PW2"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    with pytest.raises(BadRequestError, match="현재 비밀번호가 일치하지 않습니다"):
        await service.change_password(user, "wrongPass1", "newPass1")


@pytest.mark.asyncio
async def test_change_password_new_too_short(db_session):
    """새 비밀번호가 8자 미만일 때 BadRequestError 검증. (요구사항 8.4)"""
    user = await create_test_user(
        db_session, email="pw3@test.com", password="oldPass1", nickname="PW3"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    with pytest.raises(BadRequestError, match="비밀번호는 8자 이상, 영문과 숫자를 포함해야 합니다"):
        await service.change_password(user, "oldPass1", "short1")


@pytest.mark.asyncio
async def test_change_password_new_no_digit(db_session):
    """새 비밀번호에 숫자가 없을 때 BadRequestError 검증. (요구사항 8.4)"""
    user = await create_test_user(
        db_session, email="pw4@test.com", password="oldPass1", nickname="PW4"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    with pytest.raises(BadRequestError, match="비밀번호는 8자 이상, 영문과 숫자를 포함해야 합니다"):
        await service.change_password(user, "oldPass1", "nodigitpass")


@pytest.mark.asyncio
async def test_change_password_new_no_letter(db_session):
    """새 비밀번호에 영문이 없을 때 BadRequestError 검증. (요구사항 8.4)"""
    user = await create_test_user(
        db_session, email="pw5@test.com", password="oldPass1", nickname="PW5"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    with pytest.raises(BadRequestError, match="비밀번호는 8자 이상, 영문과 숫자를 포함해야 합니다"):
        await service.change_password(user, "oldPass1", "12345678")
