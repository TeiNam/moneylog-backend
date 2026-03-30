"""
OAuth Router 단위 테스트.

각 제공자별 인가 URL 반환, 콜백 처리(TokenResponse 반환),
이메일/비밀번호 가입 충돌 시 409 응답, OAuth 제공자 통신 오류 시 502 응답을 검증한다.

Requirements: 5.1, 5.2, 5.4, 5.8, 5.9
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import ConflictError, ExternalServiceError
from app.main import app
from app.models.enums import OAuthProvider
from app.schemas.auth import TokenResponse


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    """인증 불필요한 OAuth 엔드포인트용 AsyncClient를 제공한다."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 1. GET /api/v1/auth/oauth/{provider}/authorize — 인가 URL 정상 반환
#    Requirements: 5.1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["KAKAO", "NAVER", "GOOGLE", "APPLE"])
async def test_authorize_returns_url_for_each_provider(client, provider):
    """각 OAuth 제공자별 인가 URL이 정상 반환되는지 검증한다."""
    with patch("app.api.auth.OAuthService") as MockOAuthService:
        mock_instance = MockOAuthService.return_value
        mock_instance.get_authorization_url.return_value = (
            f"https://example.com/oauth/{provider.lower()}/authorize?client_id=test",
            "test-csrf-state",
        )

        response = await client.get(f"/api/v1/auth/oauth/{provider}/authorize")

    assert response.status_code == 200

    body = response.json()
    assert "authorization_url" in body
    assert "state" in body
    assert provider.lower() in body["authorization_url"]


# ---------------------------------------------------------------------------
# 2. POST /api/v1/auth/oauth/{provider}/callback — TokenResponse 반환
#    Requirements: 5.2, 5.4
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["KAKAO", "NAVER", "GOOGLE", "APPLE"])
async def test_callback_returns_token_response(client, provider):
    """인가 코드로 콜백 처리 시 access_token, refresh_token이 반환되는지 검증한다."""
    mock_token = TokenResponse(
        access_token="test-access-token",
        refresh_token="test-refresh-token",
    )

    with patch("app.api.auth.OAuthService") as MockOAuthService:
        mock_instance = MockOAuthService.return_value
        mock_instance.authenticate = AsyncMock(return_value=mock_token)

        response = await client.post(
            f"/api/v1/auth/oauth/{provider}/callback",
            json={"code": "test-auth-code", "state": "test-csrf-state"},
        )

    assert response.status_code == 200

    body = response.json()
    assert body["access_token"] == "test-access-token"
    assert body["refresh_token"] == "test-refresh-token"
    assert body["token_type"] == "bearer"


# ---------------------------------------------------------------------------
# 3. 이메일/비밀번호 가입 사용자가 동일 이메일 소셜 로그인 시 HTTP 409
#    Requirements: 5.9
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_callback_conflict_returns_409(client):
    """이미 이메일/비밀번호로 가입된 사용자가 소셜 로그인 시 409 응답을 반환하는지 검증한다."""
    with patch("app.api.auth.OAuthService") as MockOAuthService:
        mock_instance = MockOAuthService.return_value
        mock_instance.authenticate = AsyncMock(
            side_effect=ConflictError(detail="이미 이메일로 가입된 계정입니다")
        )

        response = await client.post(
            "/api/v1/auth/oauth/KAKAO/callback",
            json={"code": "test-auth-code", "state": "test-csrf-state"},
        )

    assert response.status_code == 409

    body = response.json()
    assert body["error_code"] == "CONFLICT_ERROR"
    assert "이미 이메일로 가입된 계정입니다" in body["message"]


# ---------------------------------------------------------------------------
# 4. OAuth 제공자 통신 오류 시 HTTP 502 응답
#    Requirements: 5.8
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_callback_external_error_returns_502(client):
    """OAuth 제공자 통신 오류 시 HTTP 502 응답을 반환하는지 검증한다."""
    with patch("app.api.auth.OAuthService") as MockOAuthService:
        mock_instance = MockOAuthService.return_value
        mock_instance.authenticate = AsyncMock(
            side_effect=ExternalServiceError(
                detail="소셜 로그인 처리 중 오류가 발생했습니다"
            )
        )

        response = await client.post(
            "/api/v1/auth/oauth/GOOGLE/callback",
            json={"code": "invalid-code", "state": "test-csrf-state"},
        )

    assert response.status_code == 502

    body = response.json()
    assert body["error_code"] == "EXTERNAL_SERVICE_ERROR"
    assert "소셜 로그인 처리 중 오류가 발생했습니다" in body["message"]
