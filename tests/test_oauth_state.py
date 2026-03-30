"""
OAuth state HMAC 서명 단위 테스트.

OAuthService의 _generate_signed_state / _verify_signed_state 메서드에 대한
단위 테스트를 작성한다. stateless CSRF 방어 메커니즘의 정확성을 검증한다.

테스트 케이스:
  - 생성 직후 검증 → True (왕복 검증)
  - 임의 문자열(위조) → False
  - 만료된 state → False
  - 형식이 잘못된 state (`:` 구분자 부족) → False
  - 타임스탬프가 숫자가 아닌 경우 → False
  - 서명이 변조된 경우 → False
"""

from unittest.mock import patch

from app.core.config import Settings
from app.services.oauth_service import OAuthService


# ---------------------------------------------------------------------------
# 테스트용 Settings 및 OAuthService 헬퍼
# ---------------------------------------------------------------------------

def _create_service() -> OAuthService:
    """테스트용 OAuthService 인스턴스를 생성한다."""
    mock_settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test-secret-key-for-state-tests",
    )
    return OAuthService(user_repo=None, settings=mock_settings)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. 왕복 검증: 생성 직후 검증 → True
# ---------------------------------------------------------------------------

def test_generate_then_verify_returns_true():
    """생성된 state를 즉시 검증하면 True를 반환해야 한다."""
    service = _create_service()
    state = service._generate_signed_state()
    assert service._verify_signed_state(state) is True


# ---------------------------------------------------------------------------
# 2. 임의 문자열(위조) → False
# ---------------------------------------------------------------------------

def test_forged_random_string_returns_false():
    """임의의 문자열은 검증에 실패해야 한다."""
    service = _create_service()
    assert service._verify_signed_state("completely-random-forged-string") is False


# ---------------------------------------------------------------------------
# 3. 만료된 state → False (time.time 모킹)
# ---------------------------------------------------------------------------

def test_expired_state_returns_false():
    """max_age를 초과한 state는 검증에 실패해야 한다."""
    service = _create_service()

    # 현재 시간으로 state 생성
    state = service._generate_signed_state(max_age=60)

    # 시간을 61초 뒤로 이동시켜 만료 상태를 시뮬레이션
    import time
    future_time = time.time() + 61

    with patch("app.services.oauth_service.time.time", return_value=future_time):
        assert service._verify_signed_state(state, max_age=60) is False


# ---------------------------------------------------------------------------
# 4. 형식이 잘못된 state (`:` 구분자 부족) → False
# ---------------------------------------------------------------------------

def test_malformed_state_missing_separator_returns_false():
    """`:` 구분자가 부족한 state는 검증에 실패해야 한다."""
    service = _create_service()
    # 구분자가 하나뿐인 경우 (parts가 2개)
    assert service._verify_signed_state("nonce:timestamp") is False
    # 구분자가 없는 경우 (parts가 1개)
    assert service._verify_signed_state("no-separator-at-all") is False


# ---------------------------------------------------------------------------
# 5. 타임스탬프가 숫자가 아닌 경우 → False
# ---------------------------------------------------------------------------

def test_non_numeric_timestamp_returns_false():
    """타임스탬프 부분이 숫자가 아닌 state는 검증에 실패해야 한다."""
    service = _create_service()
    assert service._verify_signed_state("nonce:not_a_number:abcdef1234567890") is False


# ---------------------------------------------------------------------------
# 6. 서명이 변조된 경우 → False
# ---------------------------------------------------------------------------

def test_tampered_signature_returns_false():
    """서명 부분이 변조된 state는 검증에 실패해야 한다."""
    service = _create_service()
    state = service._generate_signed_state()

    # state에서 서명 부분만 변조
    parts = state.split(":")
    assert len(parts) == 3, "state 형식이 nonce:timestamp:signature 이어야 한다"
    # 서명을 다른 값으로 교체
    tampered_state = f"{parts[0]}:{parts[1]}:{'0' * 16}"
    assert service._verify_signed_state(tampered_state) is False
