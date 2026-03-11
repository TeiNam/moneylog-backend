"""
회원 탈퇴 및 프로필 수정 단위 테스트.

EmailAuthService의 deactivate_account, update_profile, login 메서드를 검증한다.
- 회원 탈퇴 정상 동작 (status → WITHDRAWN)
- 탈퇴 시 비밀번호 불일치 BadRequestError
- 탈퇴 후 로그인 거부 (InvalidCredentialsError)
- 프로필 수정 정상 동작
- 닉네임 길이 제한

요구사항: 9.1~9.6, 10.1~10.5
"""

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestError, InvalidCredentialsError
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UpdateProfileRequest
from app.services.auth_service import EmailAuthService
from tests.conftest import create_test_user


# ══════════════════════════════════════════════
# 회원 탈퇴 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_deactivate_account_success(db_session):
    """회원 탈퇴 정상 동작: status가 WITHDRAWN으로 변경된다. (요구사항 9.1, 9.2)"""
    user = await create_test_user(
        db_session, email="deact@test.com", password="testPass1", nickname="탈퇴유저"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    await service.deactivate_account(user, "testPass1")

    # DB에서 사용자를 다시 조회하여 status 확인
    updated_user = await repo.get_by_id(user.id)
    assert updated_user is not None
    assert updated_user.status == "WITHDRAWN"


@pytest.mark.asyncio
async def test_deactivate_account_wrong_password(db_session):
    """탈퇴 시 비밀번호 불일치 → BadRequestError 발생. (요구사항 9.3)"""
    user = await create_test_user(
        db_session, email="deact2@test.com", password="testPass1", nickname="탈퇴유저2"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    with pytest.raises(BadRequestError, match="비밀번호가 일치하지 않습니다"):
        await service.deactivate_account(user, "wrongPass1")


@pytest.mark.asyncio
async def test_deactivate_account_then_login_rejected(db_session):
    """탈퇴 후 로그인 시도 시 InvalidCredentialsError 발생. (요구사항 9.4)"""
    # 이메일 인증 완료된 사용자 생성
    user = await create_test_user(
        db_session,
        email="deact3@test.com",
        password="testPass1",
        nickname="탈퇴유저3",
        email_verified=True,
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    # 회원 탈퇴 수행
    await service.deactivate_account(user, "testPass1")

    # 탈퇴 후 로그인 시도 → InvalidCredentialsError
    with pytest.raises(InvalidCredentialsError):
        await service.login("deact3@test.com", "testPass1")


# ══════════════════════════════════════════════
# 프로필 수정 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_profile_success(db_session):
    """프로필 수정 정상 동작: 닉네임과 프로필 이미지가 갱신된다. (요구사항 10.1)"""
    user = await create_test_user(
        db_session, email="profile@test.com", password="testPass1", nickname="기존닉네임"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    data = UpdateProfileRequest(nickname="새닉네임", profile_image="https://example.com/img.png")
    updated_user = await service.update_profile(user, data)

    assert updated_user.nickname == "새닉네임"
    assert updated_user.profile_image == "https://example.com/img.png"


@pytest.mark.asyncio
async def test_update_profile_nickname_only(db_session):
    """닉네임만 변경 시 프로필 이미지는 변경되지 않는다. (요구사항 10.1)"""
    user = await create_test_user(
        db_session, email="profile2@test.com", password="testPass1", nickname="기존닉네임2"
    )
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    data = UpdateProfileRequest(nickname="변경닉네임")
    updated_user = await service.update_profile(user, data)

    assert updated_user.nickname == "변경닉네임"


@pytest.mark.asyncio
async def test_update_profile_nickname_too_short():
    """닉네임이 2자 미만이면 ValidationError 발생. (요구사항 10.2, 10.3)"""
    with pytest.raises(ValidationError):
        UpdateProfileRequest(nickname="A")


@pytest.mark.asyncio
async def test_update_profile_nickname_too_long():
    """닉네임이 20자 초과이면 ValidationError 발생. (요구사항 10.2, 10.3)"""
    with pytest.raises(ValidationError):
        UpdateProfileRequest(nickname="A" * 21)
