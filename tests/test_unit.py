"""
단위 테스트 모듈.

헬스체크 엔드포인트 및 인증 미들웨어의 단위 테스트를 포함한다.
"""

import pytest

from app.core.security import create_access_token


# ---------------------------------------------------------------------------
# 태스크 5.2: 헬스체크 엔드포인트 단위 테스트
# Feature: moneylog-backend-phase1
# **Validates: Requirements 1.4, 3.4**
# ---------------------------------------------------------------------------


async def test_health_endpoint_response_format(client):
    """GET /health 정상 응답 형식 검증 (status, database, version 필드)."""
    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "version" in data
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# 태스크 12.2: 인증 미들웨어 단위 테스트
# Feature: moneylog-backend-phase1
# **Validates: Requirements 11.1, 11.2, 11.3**
# ---------------------------------------------------------------------------


async def test_auth_middleware_missing_header(client):
    """Authorization 헤더 누락 시 GET /api/v1/auth/me → 401 응답."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_auth_middleware_invalid_token(client):
    """잘못된 형식 토큰 시 GET /api/v1/auth/me → 401 응답."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token-here"},
    )
    assert response.status_code == 401


async def test_auth_middleware_valid_token(client, db_session):
    """유효한 토큰으로 사용자 정보 반환 검증."""
    from tests.conftest import create_test_user

    user = await create_test_user(
        db_session,
        email="middleware_test@example.com",
        password="validPass1",
        nickname="미들웨어테스트",
        email_verified=True,
    )
    await db_session.commit()

    # 유효한 액세스 토큰 생성
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "auth_provider": user.auth_provider,
    })

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "middleware_test@example.com"
    assert data["nickname"] == "미들웨어테스트"
    assert data["auth_provider"] == "EMAIL"
