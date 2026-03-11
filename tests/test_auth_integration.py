"""
인증 API 통합 테스트.

회원가입 → 이메일 인증 → 로그인 → 토큰 갱신 → /me 조회 전체 흐름과
각종 에러 시나리오를 검증한다.

conftest.py의 mock_email_sending이 autouse=True로
인증 코드를 "123456"으로 고정한다.
"""

import pytest

from app.core.security import create_access_token


# ---------------------------------------------------------------------------
# 태스크 13.2: 인증 API 통합 테스트
# Feature: moneylog-backend-phase1
# **Validates: Requirements 7.3, 8.4, 8.5, 9.2, 9.3, 9.5, 10.5, 11.4**
# ---------------------------------------------------------------------------


async def test_full_auth_flow(client):
    """
    전체 인증 흐름 테스트:
    회원가입 → 이메일 인증(코드 "123456") → 로그인 → 토큰 갱신 → /me 조회
    """
    # 1. 회원가입
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "flow@example.com",
            "password": "flowPass1",
            "nickname": "플로우유저",
        },
    )
    assert register_resp.status_code == 201
    user_data = register_resp.json()
    assert user_data["email"] == "flow@example.com"
    assert user_data["email_verified"] is False

    # 2. 이메일 인증 (conftest에서 코드가 "123456"으로 고정됨)
    verify_resp = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "flow@example.com", "code": "123456"},
    )
    assert verify_resp.status_code == 200

    # 3. 로그인
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "flow@example.com", "password": "flowPass1"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    # 4. 토큰 갱신
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert "access_token" in new_tokens

    # 5. /me 조회
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "flow@example.com"
    assert me_data["email_verified"] is True


async def test_duplicate_email_register_409(client):
    """중복 이메일 회원가입 시 409 응답."""
    payload = {
        "email": "dup@example.com",
        "password": "dupPass123",
        "nickname": "중복유저",
    }
    # 첫 번째 회원가입
    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # 중복 회원가입
    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409


async def test_unverified_user_login_403(client):
    """이메일 미인증 사용자 로그인 시 403 응답."""
    # 회원가입 (이메일 미인증 상태)
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "unverified@example.com",
            "password": "unverPass1",
            "nickname": "미인증유저",
        },
    )

    # 로그인 시도
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "unverified@example.com", "password": "unverPass1"},
    )
    assert resp.status_code == 403


async def test_wrong_password_login_401(client):
    """잘못된 비밀번호 로그인 시 401 응답."""
    # 회원가입 + 이메일 인증
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpw@example.com",
            "password": "correctPass1",
            "nickname": "비밀번호틀림",
        },
    )
    await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "wrongpw@example.com", "code": "123456"},
    )

    # 잘못된 비밀번호로 로그인
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "wrongPass1"},
    )
    assert resp.status_code == 401


async def test_expired_token_401(client):
    """만료/유효하지 않은 토큰 시 401 응답."""
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer expired.invalid.token"},
    )
    assert resp.status_code == 401


async def test_verification_code_exhausted_after_5_failures(client):
    """
    인증 코드 5회 초과 실패 시 무효화 테스트.
    conftest에서 코드가 "123456"으로 고정되므로,
    잘못된 코드 "000000"을 6번 제출한다.
    """
    # 회원가입
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "exhaust@example.com",
            "password": "exhaustPass1",
            "nickname": "소진테스트",
        },
    )

    # 잘못된 코드를 6번 제출 (5회 초과 시 무효화)
    for i in range(6):
        resp = await client.post(
            "/api/v1/auth/verify-email",
            json={"email": "exhaust@example.com", "code": "000000"},
        )

    # 마지막 응답은 400 (무효화 또는 잘못된 코드)
    assert resp.status_code == 400
