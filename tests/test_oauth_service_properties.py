"""
OAuth 서비스 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 OAuth 소셜 로그인 서비스의 핵심 속성을 검증한다.
HTTP 호출과 UserRepository는 모킹하여 순수 비즈니스 로직만 테스트한다.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st
from jose import jwt as jose_jwt

from app.core.config import Settings
from app.models.enums import OAuthProvider
from app.schemas.auth import TokenResponse
from app.services.oauth_service import OAuthService


# ---------------------------------------------------------------------------
# 테스트용 전략(Strategy) 정의
# ---------------------------------------------------------------------------

# OAuth 제공자 전략
provider_strategy = st.sampled_from(list(OAuthProvider))

# 이메일 전략 — 유효한 이메일 형식
email_strategy = st.from_regex(
    r"[a-z][a-z0-9]{2,10}@[a-z]{3,8}\.(com|net|org)",
    fullmatch=True,
)

# 닉네임 전략
nickname_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)

# Apple Private Email Relay 이메일 전략
apple_private_email_strategy = st.from_regex(
    r"[a-z0-9]{8,16}@privaterelay\.appleid\.com",
    fullmatch=True,
)

# Apple sub claim 전략 (고유 식별자)
apple_sub_strategy = st.from_regex(r"[0-9]{6}\.[a-f0-9]{32}\.[0-9]{4}", fullmatch=True)

# 일반 sub claim 전략
sub_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=8,
    max_size=32,
)

# 불리언 전략
bool_strategy = st.booleans()


# ---------------------------------------------------------------------------
# 테스트용 Settings 헬퍼
# ---------------------------------------------------------------------------

def _create_test_settings() -> Settings:
    """테스트용 Settings 인스턴스를 생성한다."""
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test-secret-key-for-oauth-tests",
        KAKAO_CLIENT_ID="test-kakao-id",
        KAKAO_CLIENT_SECRET="test-kakao-secret",
        KAKAO_REDIRECT_URI="http://localhost/callback/kakao",
        NAVER_CLIENT_ID="test-naver-id",
        NAVER_CLIENT_SECRET="test-naver-secret",
        NAVER_REDIRECT_URI="http://localhost/callback/naver",
        GOOGLE_CLIENT_ID="test-google-id",
        GOOGLE_CLIENT_SECRET="test-google-secret",
        GOOGLE_REDIRECT_URI="http://localhost/callback/google",
        APPLE_CLIENT_ID="com.test.moneylog",
        APPLE_TEAM_ID="TESTTEAMID",
        APPLE_KEY_ID="TESTKEYID",
        APPLE_PRIVATE_KEY="test-private-key",
        APPLE_REDIRECT_URI="http://localhost/callback/apple",
    )


# ---------------------------------------------------------------------------
# 헬퍼: 제공자별 모킹된 토큰 교환 및 프로필 응답 생성
# ---------------------------------------------------------------------------

def _mock_token_response(provider: OAuthProvider, email: str, nickname: str, sub: str = ""):
    """제공자별 토큰 교환 및 프로필 API 응답을 모킹하기 위한 httpx 응답을 생성한다."""
    if provider == OAuthProvider.KAKAO:
        token_json = {"access_token": "kakao-access-token"}
        profile_json = {
            "kakao_account": {
                "email": email,
                "profile": {"nickname": nickname, "profile_image_url": None},
            }
        }
        return token_json, profile_json

    if provider == OAuthProvider.NAVER:
        token_json = {"access_token": "naver-access-token"}
        profile_json = {
            "response": {
                "email": email,
                "nickname": nickname,
                "profile_image": None,
            }
        }
        return token_json, profile_json

    if provider == OAuthProvider.GOOGLE:
        token_json = {"access_token": "google-access-token"}
        profile_json = {
            "email": email,
            "name": nickname,
            "picture": None,
        }
        return token_json, profile_json

    if provider == OAuthProvider.APPLE:
        # Apple은 id_token JWT를 생성하여 반환
        claims = {
            "sub": sub or "apple-sub-12345",
            "email": email,
            "email_verified": True,
            "is_private_email": False,
        }
        id_token = jose_jwt.encode(claims, "secret", algorithm="HS256")
        token_json = {"access_token": "apple-access-token", "id_token": id_token}
        return token_json, None  # Apple은 프로필 API 호출 없음

    raise ValueError(f"지원하지 않는 제공자: {provider}")


def _create_mock_user(email: str, nickname: str, provider: OAuthProvider):
    """모킹된 User 객체를 생성한다."""
    user = MagicMock()
    user.id = uuid4()
    user.email = email
    user.nickname = nickname
    user.auth_provider = provider.value
    user.password_hash = None
    user.email_verified = True
    user.status = "ACTIVE"
    user.profile_image = None
    return user


def _setup_httpx_mock(token_json, profile_json):
    """httpx.AsyncClient를 모킹하여 토큰 교환 및 프로필 조회 응답을 설정한다."""
    call_count = 0

    async def mock_post(*args, **kwargs):
        resp = MagicMock()
        resp.json.return_value = token_json
        resp.raise_for_status = MagicMock()
        return resp

    async def mock_get(*args, **kwargs):
        resp = MagicMock()
        resp.json.return_value = profile_json
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# Property 10: 소셜 로그인 신규 사용자 생성 불변식
# Feature: frontend-integration-improvements, Property 10: 소셜 로그인 신규 사용자 생성 불변식
# **Validates: Requirements 5.3, 5.6, 5.7, 5.12**
# ---------------------------------------------------------------------------


@hypothesis_settings(max_examples=30, deadline=None)
@given(
    provider=provider_strategy,
    email=email_strategy,
    nickname=nickname_strategy.filter(lambda n: len(n) > 0),
)
def test_oauth_new_user_creation_invariant(
    provider: OAuthProvider, email: str, nickname: str
):
    """임의의 OAuth 제공자와 유효한 이메일/닉네임에 대해,
    해당 이메일의 사용자가 존재하지 않을 때 OAuth 인증을 수행하면,
    생성된 사용자의 auth_provider는 해당 제공자명과 일치하고,
    password_hash는 None이며, email_verified는 True여야 한다.
    """
    settings = _create_test_settings()

    # UserRepository 모킹
    mock_repo = AsyncMock()
    mock_repo.get_by_email.return_value = None  # 사용자 없음

    # create가 호출되면 전달된 데이터로 User 객체 생성
    created_user_data = {}

    async def mock_create(data):
        created_user_data.update(data)
        return _create_mock_user(
            email=data["email"],
            nickname=data["nickname"],
            provider=OAuthProvider(data["auth_provider"]),
        )

    mock_repo.create = mock_create

    # 토큰 교환 및 프로필 응답 모킹
    token_json, profile_json = _mock_token_response(provider, email, nickname)
    mock_client = _setup_httpx_mock(token_json, profile_json)

    service = OAuthService(user_repo=mock_repo, settings=settings)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         patch.object(service, "_generate_apple_client_secret", return_value="mocked-apple-secret"):
        result = asyncio.get_event_loop().run_until_complete(
            service.authenticate(provider, "test-auth-code")
        )

    # 검증: 신규 사용자 생성 데이터 확인
    assert created_user_data["auth_provider"] == provider.value, (
        f"auth_provider 불일치: {created_user_data['auth_provider']} != {provider.value}"
    )
    assert created_user_data["password_hash"] is None, (
        f"password_hash가 None이 아님: {created_user_data['password_hash']}"
    )
    assert created_user_data["email_verified"] is True, (
        f"email_verified가 True가 아님: {created_user_data['email_verified']}"
    )

    # 검증: TokenResponse 반환
    assert isinstance(result, TokenResponse)
    assert result.access_token
    assert result.refresh_token


@hypothesis_settings(max_examples=30, deadline=None)
@given(
    apple_email=apple_private_email_strategy,
    nickname=nickname_strategy.filter(lambda n: len(n) > 0),
)
def test_oauth_apple_private_email_relay_stored_as_is(
    apple_email: str, nickname: str
):
    """Apple Private Email Relay 시 프록시 이메일(@privaterelay.appleid.com)이
    그대로 저장되어야 한다.
    """
    settings = _create_test_settings()
    provider = OAuthProvider.APPLE

    mock_repo = AsyncMock()
    mock_repo.get_by_email.return_value = None

    created_user_data = {}

    async def mock_create(data):
        created_user_data.update(data)
        return _create_mock_user(
            email=data["email"],
            nickname=data["nickname"],
            provider=OAuthProvider.APPLE,
        )

    mock_repo.create = mock_create

    # Apple id_token에 Private Email Relay 이메일 포함
    claims = {
        "sub": "apple-sub-private-12345",
        "email": apple_email,
        "email_verified": True,
        "is_private_email": True,
    }
    id_token = jose_jwt.encode(claims, "secret", algorithm="HS256")
    token_json = {"access_token": "apple-access-token", "id_token": id_token}
    mock_client = _setup_httpx_mock(token_json, None)

    service = OAuthService(user_repo=mock_repo, settings=settings)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         patch.object(service, "_generate_apple_client_secret", return_value="mocked-apple-secret"):
        asyncio.get_event_loop().run_until_complete(
            service.authenticate(provider, "test-auth-code")
        )

    # 검증: 프록시 이메일이 그대로 저장됨
    assert created_user_data["email"] == apple_email, (
        f"Apple 프록시 이메일 불일치: {created_user_data['email']} != {apple_email}"
    )
    assert "@privaterelay.appleid.com" in created_user_data["email"]


# ---------------------------------------------------------------------------
# Property 11: 소셜 로그인 기존 사용자 토큰 발급
# Feature: frontend-integration-improvements, Property 11: 소셜 로그인 기존 사용자 토큰 발급
# **Validates: Requirements 5.4, 5.5**
# ---------------------------------------------------------------------------


@hypothesis_settings(max_examples=30, deadline=None)
@given(
    provider=provider_strategy,
    email=email_strategy,
    nickname=nickname_strategy.filter(lambda n: len(n) > 0),
)
def test_oauth_existing_user_token_issuance(
    provider: OAuthProvider, email: str, nickname: str
):
    """임의의 OAuth 제공자와 이미 해당 제공자로 가입된 사용자에 대해,
    OAuth 인증을 수행하면 access_token과 refresh_token을 모두 포함하는
    TokenResponse가 반환되어야 한다.
    """
    settings = _create_test_settings()

    # 기존 OAuth 사용자 모킹
    existing_user = _create_mock_user(email, nickname, provider)
    existing_user.auth_provider = provider.value
    existing_user.password_hash = None  # OAuth 사용자는 password_hash가 None

    mock_repo = AsyncMock()
    mock_repo.get_by_email.return_value = existing_user
    mock_repo.update.return_value = existing_user

    # 토큰 교환 및 프로필 응답 모킹
    token_json, profile_json = _mock_token_response(provider, email, nickname)
    mock_client = _setup_httpx_mock(token_json, profile_json)

    service = OAuthService(user_repo=mock_repo, settings=settings)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client), \
         patch.object(service, "_generate_apple_client_secret", return_value="mocked-apple-secret"):
        result = asyncio.get_event_loop().run_until_complete(
            service.authenticate(provider, "test-auth-code")
        )

    # 검증: TokenResponse에 access_token과 refresh_token이 모두 포함
    assert isinstance(result, TokenResponse), f"반환 타입 불일치: {type(result)}"
    assert result.access_token, "access_token이 비어있음"
    assert result.refresh_token, "refresh_token이 비어있음"
    assert result.token_type == "bearer", f"token_type 불일치: {result.token_type}"

    # 검증: create가 호출되지 않음 (기존 사용자이므로 신규 생성 없음)
    mock_repo.create.assert_not_called()


# ---------------------------------------------------------------------------
# Property 12: Apple id_token JWT 파싱 및 사용자 식별
# Feature: frontend-integration-improvements, Property 12: Apple id_token JWT 파싱 및 사용자 식별
# **Validates: Requirements 5.11, 5.13**
# ---------------------------------------------------------------------------


@hypothesis_settings(max_examples=30, deadline=None)
@given(
    sub=sub_strategy,
    email=email_strategy,
    email_verified=bool_strategy,
    is_private_email=bool_strategy,
)
def test_apple_id_token_parsing_and_user_identification(
    sub: str, email: str, email_verified: bool, is_private_email: bool
):
    """임의의 유효한 Apple id_token JWT claims(sub, email, email_verified, is_private_email)에 대해,
    _decode_apple_id_token으로 파싱한 결과는 원본 claims의 sub, email 값과 일치해야 하며,
    이메일이 없거나 숨겨진 경우에도 sub claim으로 사용자를 고유하게 식별할 수 있어야 한다.
    """
    settings = _create_test_settings()
    service = OAuthService(user_repo=None, settings=settings)  # type: ignore[arg-type]

    # Apple id_token JWT 생성
    claims = {
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "is_private_email": is_private_email,
    }
    id_token = jose_jwt.encode(claims, "secret", algorithm="HS256")

    # 파싱
    result = service._decode_apple_id_token(id_token)

    # 검증: sub claim이 원본과 일치
    assert result["sub"] == sub, f"sub 불일치: {result['sub']} != {sub}"

    # 검증: email claim이 원본과 일치
    assert result["email"] == email, f"email 불일치: {result['email']} != {email}"

    # 검증: email_verified claim이 원본과 일치
    assert result["email_verified"] == email_verified, (
        f"email_verified 불일치: {result['email_verified']} != {email_verified}"
    )

    # 검증: is_private_email claim이 원본과 일치
    assert result["is_private_email"] == is_private_email, (
        f"is_private_email 불일치: {result['is_private_email']} != {is_private_email}"
    )

    # 검증: sub claim은 항상 존재하며 비어있지 않음 (사용자 식별 가능)
    assert result["sub"], "sub claim이 비어있어 사용자 식별 불가"


@hypothesis_settings(max_examples=30, deadline=None)
@given(sub=sub_strategy)
def test_apple_id_token_hidden_email_sub_identification(sub: str):
    """이메일이 없는 경우에도 sub claim으로 사용자를 고유하게 식별할 수 있어야 한다."""
    settings = _create_test_settings()
    service = OAuthService(user_repo=None, settings=settings)  # type: ignore[arg-type]

    # 이메일 없는 Apple id_token JWT 생성
    claims = {
        "sub": sub,
        "email_verified": False,
        "is_private_email": True,
    }
    id_token = jose_jwt.encode(claims, "secret", algorithm="HS256")

    result = service._decode_apple_id_token(id_token)

    # 검증: email이 None이어도 sub로 식별 가능
    assert result["email"] is None, f"email이 None이 아님: {result['email']}"
    assert result["sub"] == sub, f"sub 불일치: {result['sub']} != {sub}"
    assert result["sub"], "sub claim이 비어있어 사용자 식별 불가"
