"""
버그 조건 탐색 속성 기반 테스트 (Bug Condition Exploration PBT).

수정 전 코드에서 반드시 FAIL해야 한다 — 실패가 버그 존재를 증명한다.
수정 후 코드에서 PASS하면 버그가 해결된 것이다.

테스트 대상 버그 조건:
  - condition3: refresh 토큰이 access 토큰처럼 동작 (get_current_user 타입 미검증)
  - condition7: verify_password의 포괄적 예외 처리 (non-ValueError도 False 반환)
  - condition8: register 시드 생성의 포괄적 예외 처리 (인프라 오류 억제)

**Validates: Requirements 1.3, 1.7, 1.8**
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.exceptions import AppException, InvalidCredentialsError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    hash_password,
)


# ---------------------------------------------------------------------------
# 전략(Strategy) 정의
# ---------------------------------------------------------------------------

# 유효한 사용자 데이터 생성 전략
_user_data_strategy = st.fixed_dictionaries({
    "sub": st.uuids().map(str),
    "email": st.emails(),
    "auth_provider": st.sampled_from(["EMAIL", "KAKAO", "NAVER", "GOOGLE", "APPLE"]),
})

# ValueError가 아닌 예외 타입 전략
_non_value_error_strategy = st.sampled_from([
    RuntimeError("런타임 오류"),
    TypeError("타입 오류"),
    OSError("OS 오류"),
    MemoryError("메모리 오류"),
])

# 인프라 오류 전략 (DB 연결 실패 등)
_infrastructure_error_strategy = st.sampled_from([
    OSError("DB 연결 실패"),
    ConnectionError("네트워크 오류"),
    TimeoutError("DB 타임아웃"),
    RuntimeError("인프라 장애"),
])


# ---------------------------------------------------------------------------
# condition3: refresh 토큰(type="refresh")을 Bearer 토큰으로 전달 시
#             get_current_user가 거부하지 않음
# 기대 동작: InvalidCredentialsError 발생
# 현재 동작(버그): refresh 토큰이 access 토큰처럼 동작하여 사용자 반환
# **Validates: Requirements 1.3**
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(user_data=_user_data_strategy)
@pytest.mark.asyncio
async def test_condition3_refresh_token_rejected_by_get_current_user(user_data: dict):
    """
    condition3: 임의의 사용자 데이터로 생성한 refresh 토큰을
    get_current_user에 전달하면 InvalidCredentialsError가 발생해야 한다.

    현재 코드는 토큰의 type 필드를 검증하지 않아 refresh 토큰이
    access 토큰처럼 동작한다 → 이 테스트는 FAIL해야 한다.

    **Validates: Requirements 1.3**
    """
    # refresh 토큰 생성 (type="refresh" 포함)
    refresh_token = create_refresh_token(user_data)

    # 토큰 디코딩하여 type 필드 확인
    payload = decode_token(refresh_token)
    assert payload["type"] == "refresh", "생성된 토큰이 refresh 타입이어야 한다"

    # get_current_user 의존성에서 refresh 토큰을 거부해야 한다
    from app.core.dependencies import get_current_user

    # DB 세션과 사용자 조회를 모킹
    mock_user = MagicMock()
    mock_user.id = uuid.UUID(user_data["sub"])
    mock_user.email = user_data["email"]

    mock_db = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = mock_user

    with patch("app.core.dependencies.UserRepository", return_value=mock_repo):
        # refresh 토큰으로 get_current_user 호출 시 InvalidCredentialsError 기대
        with pytest.raises(InvalidCredentialsError):
            await get_current_user(token=refresh_token, db=mock_db)


# ---------------------------------------------------------------------------
# condition7: verify_password에서 ValueError가 아닌 예외도 False로 처리됨
# 기대 동작: non-ValueError 예외는 상위로 전파
# 현재 동작(버그): except Exception으로 모든 예외를 잡고 False 반환
# **Validates: Requirements 1.7**
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(exception=_non_value_error_strategy)
def test_condition7_verify_password_propagates_non_value_errors(exception: Exception):
    """
    condition7: bcrypt.checkpw에서 ValueError가 아닌 예외가 발생하면
    verify_password는 해당 예외를 상위로 전파해야 한다.

    현재 코드는 except Exception으로 모든 예외를 잡고 False를 반환하여
    실제 버그가 은폐된다 → 이 테스트는 FAIL해야 한다.

    **Validates: Requirements 1.7**
    """
    # 유효한 bcrypt 해시를 사용하여 인코딩 문제 방지
    valid_hash = hash_password("dummy_password")

    with patch("app.core.security.bcrypt.checkpw", side_effect=exception):
        # non-ValueError 예외가 전파되어야 한다
        with pytest.raises(type(exception)):
            verify_password("any_password", valid_hash)


# ---------------------------------------------------------------------------
# condition8: 회원가입 시드 생성에서 인프라 오류가 except Exception으로 억제됨
# 기대 동작: 인프라 오류(OperationalError 등)는 상위로 전파
# 현재 동작(버그): except Exception으로 모든 예외를 잡고 warning 로그만 남김
# **Validates: Requirements 1.8**
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(infra_error=_infrastructure_error_strategy)
@pytest.mark.asyncio
async def test_condition8_register_seed_propagates_infrastructure_errors(
    infra_error: Exception,
):
    """
    condition8: 회원가입 후 기본 카테고리 시드 생성에서 인프라 오류가 발생하면
    해당 오류가 상위로 전파되어야 한다.

    현재 코드는 except Exception으로 모든 예외를 잡고 warning 로그만 남겨
    심각한 인프라 문제가 무시된다 → 이 테스트는 FAIL해야 한다.

    **Validates: Requirements 1.8**
    """
    from app.api.auth import register
    from app.schemas.auth import RegisterRequest

    # 회원가입 요청 데이터
    body = RegisterRequest(
        email="test_infra@example.com",
        password="testpass1",
        nickname="테스트",
    )

    # EmailAuthService.register 모킹 — 정상 사용자 반환
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = body.email
    mock_user.nickname = body.nickname
    mock_user.auth_provider = "EMAIL"
    mock_user.status = "ACTIVE"
    mock_user.email_verified = False
    mock_user.profile_image = None
    mock_user.default_asset_id = None
    mock_user.created_at = "2024-01-01T00:00:00"
    mock_user.last_login_at = None

    mock_db = AsyncMock()

    # CategoryService.seed_defaults가 인프라 오류를 발생시키도록 모킹
    with (
        patch("app.api.auth.EmailAuthService") as mock_auth_cls,
        patch("app.api.auth.CategoryService") as mock_cat_cls,
    ):
        mock_auth_instance = AsyncMock()
        mock_auth_instance.register.return_value = mock_user
        mock_auth_cls.return_value = mock_auth_instance

        mock_cat_instance = AsyncMock()
        mock_cat_instance.seed_defaults.side_effect = infra_error
        mock_cat_cls.return_value = mock_cat_instance

        # 인프라 오류가 전파되어야 한다 (AppException이 아닌 예외)
        with pytest.raises(type(infra_error)):
            await register(body=body, db=mock_db)
