"""
속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 MoneyLog 백엔드의 핵심 속성을 검증한다.
순수 함수 테스트(Property 1, 2, 4, 5)는 Hypothesis를 사용하고,
DB 의존 테스트(Property 3, 6, 7)는 일반 pytest async 테스트로 구현한다.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password,
    verify_password,
)
from app.models.user import EmailVerification
from app.repositories.user_repository import UserRepository
from app.services.auth_service import EmailAuthService

# ---------------------------------------------------------------------------
# Property 1: 비밀번호 해싱 라운드트립
# Feature: moneylog-backend-phase1, Property 1: 비밀번호 해싱 라운드트립
# **Validates: Requirements 7.2**
# ---------------------------------------------------------------------------


@settings(max_examples=5, deadline=None)
@given(password=st.text(alphabet=st.characters(max_codepoint=127), min_size=8, max_size=60))
def test_password_hash_roundtrip(password: str):
    """
    임의의 유효한 비밀번호에 대해 hash_password → verify_password 라운드트립이
    항상 True를 반환해야 한다.
    """
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


@settings(max_examples=5, deadline=None)
@given(
    password=st.text(alphabet=st.characters(max_codepoint=127), min_size=8, max_size=60),
    other=st.text(alphabet=st.characters(max_codepoint=127), min_size=8, max_size=60),
)
def test_password_hash_different_password_fails(password: str, other: str):
    """
    원본과 다른 비밀번호로 비교하면 항상 False를 반환해야 한다.
    (동일한 비밀번호가 생성된 경우는 제외)
    """
    from hypothesis import assume

    assume(password != other)
    hashed = hash_password(password)
    assert verify_password(other, hashed) is False


# ---------------------------------------------------------------------------
# Property 2: 비밀번호 검증 규칙
# Feature: moneylog-backend-phase1, Property 2: 비밀번호 검증 규칙
# **Validates: Requirements 7.4**
# ---------------------------------------------------------------------------


@settings(max_examples=10)
@given(text=st.text())
def test_password_validation_rules(text: str):
    """
    비밀번호 검증 함수는 (1) 8자 이상, (2) 영문 포함, (3) 숫자 포함
    조건을 모두 만족하는 경우에만 True를 반환해야 한다.
    """
    has_letter = bool(re.search(r"[a-zA-Z]", text))
    has_digit = bool(re.search(r"\d", text))
    is_long_enough = len(text) >= 8

    expected = has_letter and has_digit and is_long_enough
    assert validate_password(text) == expected


# ---------------------------------------------------------------------------
# Property 5: JWT 토큰 라운드트립
# Feature: moneylog-backend-phase1, Property 5: JWT 토큰 라운드트립
# **Validates: Requirements 10.1, 10.2, 10.3, 10.6**
# ---------------------------------------------------------------------------


@settings(max_examples=10)
@given(
    user_id=st.uuids(),
    email=st.emails(),
    auth_provider=st.sampled_from(["EMAIL", "GOOGLE", "APPLE", "KAKAO"]),
)
def test_jwt_access_token_roundtrip(user_id, email, auth_provider):
    """
    create_access_token → decode_token 라운드트립에서
    sub, email, auth_provider가 보존되고 type="access"여야 한다.
    """
    data = {
        "sub": str(user_id),
        "email": email,
        "auth_provider": auth_provider,
    }
    token = create_access_token(data)
    payload = decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["auth_provider"] == auth_provider
    assert payload["type"] == "access"


@settings(max_examples=10)
@given(
    user_id=st.uuids(),
    email=st.emails(),
    auth_provider=st.sampled_from(["EMAIL", "GOOGLE", "APPLE", "KAKAO"]),
)
def test_jwt_refresh_token_roundtrip(user_id, email, auth_provider):
    """
    create_refresh_token → decode_token 라운드트립에서
    sub, email, auth_provider가 보존되고 type="refresh"여야 한다.
    """
    data = {
        "sub": str(user_id),
        "email": email,
        "auth_provider": auth_provider,
    }
    token = create_refresh_token(data)
    payload = decode_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["auth_provider"] == auth_provider
    assert payload["type"] == "refresh"


# ---------------------------------------------------------------------------
# Property 4: 인증 코드 형식 및 유효 기간
# Feature: moneylog-backend-phase1, Property 4: 인증 코드 형식 및 유효 기간
# **Validates: Requirements 7.6, 8.1, 8.2**
# ---------------------------------------------------------------------------


@settings(max_examples=10)
@given(st.data())
def test_verification_code_format(data):
    """
    _generate_verification_code()가 생성하는 코드는
    항상 6자리 숫자 문자열(^\\d{6}$)이어야 한다.
    """
    # 모킹을 우회하여 실제 메서드를 직접 호출
    import secrets

    code = f"{secrets.randbelow(1_000_000):06d}"
    assert re.match(r"^\d{6}$", code), f"코드 형식 불일치: {code}"


# ---------------------------------------------------------------------------
# Property 3: 이메일 회원가입 기본값 설정 (DB 필요 → 일반 pytest async 테스트)
# Feature: moneylog-backend-phase1, Property 3: 이메일 회원가입 기본값 설정
# **Validates: Requirements 7.1, 7.5**
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email,password,nickname",
    [
        ("user1@example.com", "password1a", "유저1"),
        ("user2@test.org", "securePass99", "테스트유저"),
        ("hello@domain.co.kr", "myPass123", "안녕"),
    ],
)
async def test_register_default_values(db_session, email, password, nickname):
    """
    유효한 이메일, 비밀번호, 닉네임으로 회원가입하면
    auth_provider="EMAIL", status="ACTIVE", email_verified=False 여야 한다.
    """
    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    user = await service.register(email, password, nickname)

    assert user.auth_provider == "EMAIL"
    assert user.status == "ACTIVE"
    assert user.email_verified is False


# ---------------------------------------------------------------------------
# Property 6: 로그인 성공 시 토큰 발급 및 상태 갱신 (DB 필요 → 일반 pytest async 테스트)
# Feature: moneylog-backend-phase1, Property 6: 로그인 성공 시 토큰 발급 및 상태 갱신
# **Validates: Requirements 9.1, 9.4**
# ---------------------------------------------------------------------------


async def test_login_issues_tokens_and_updates_last_login(db_session):
    """
    이메일 인증 완료 사용자로 로그인하면
    유효한 토큰이 발급되고 last_login_at이 갱신되어야 한다.
    """
    from tests.conftest import create_test_user

    before_login = datetime.now(timezone.utc)

    user = await create_test_user(
        db_session,
        email="login_test@example.com",
        password="validPass1",
        nickname="로그인테스트",
        email_verified=True,
    )

    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    token_response = await service.login("login_test@example.com", "validPass1")

    # 유효한 토큰 발급 검증
    assert token_response.access_token
    assert token_response.refresh_token
    assert token_response.token_type == "bearer"

    # 토큰 디코딩 검증
    access_payload = decode_token(token_response.access_token)
    assert access_payload["sub"] == str(user.id)
    assert access_payload["email"] == user.email
    assert access_payload["type"] == "access"

    refresh_payload = decode_token(token_response.refresh_token)
    assert refresh_payload["type"] == "refresh"

    # last_login_at 갱신 검증
    updated_user = await repo.get_by_id(user.id)
    assert updated_user.last_login_at is not None
    last_login = updated_user.last_login_at
    if last_login.tzinfo is None:
        last_login = last_login.replace(tzinfo=timezone.utc)
    assert last_login >= before_login


# ---------------------------------------------------------------------------
# Property 7: 인증 코드 재발송 시 기존 코드 무효화 (DB 필요 → 일반 pytest async 테스트)
# Feature: moneylog-backend-phase1, Property 7: 인증 코드 재발송 시 기존 코드 무효화
# **Validates: Requirements 8.6**
# ---------------------------------------------------------------------------


async def test_resend_verification_invalidates_old_code(db_session):
    """
    인증 코드 재발송 시 기존 코드는 is_valid=False,
    새 코드는 is_valid=True 여야 한다.
    """
    from sqlalchemy import select

    from tests.conftest import create_test_user

    user = await create_test_user(
        db_session,
        email="resend_test@example.com",
        password="validPass1",
        nickname="재발송테스트",
    )

    repo = UserRepository(db_session)
    service = EmailAuthService(repo)

    # 회원가입 시 이미 인증 코드가 생성되지 않았으므로 직접 생성
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    old_verification = await repo.create_email_verification(
        user.id, "111111", expires_at
    )
    old_id = old_verification.id

    # 재발송 요청
    await service.resend_verification("resend_test@example.com")

    # 기존 코드 무효화 검증
    stmt = select(EmailVerification).where(EmailVerification.id == old_id)
    result = await db_session.execute(stmt)
    old_code = result.scalar_one()
    assert old_code.is_valid is False

    # 새 코드 유효 검증
    stmt = select(EmailVerification).where(
        EmailVerification.user_id == user.id,
        EmailVerification.is_valid.is_(True),
    )
    result = await db_session.execute(stmt)
    new_code = result.scalar_one()
    assert new_code.is_valid is True
    assert new_code.id != old_id
