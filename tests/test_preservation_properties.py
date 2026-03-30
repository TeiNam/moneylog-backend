"""
보존 속성 기반 테스트 (Preservation Property-Based Tests).

수정 전 코드에서 반드시 PASS해야 한다 — 기존 동작의 기준선을 확인한다.
수정 후에도 PASS하면 회귀(regression)가 없음을 증명한다.

테스트 대상 보존 속성:
  - 유효한 access 토큰(type="access")으로 get_current_user 인증 성공
  - 올바른 비밀번호로 verify_password → True
  - 잘못된 비밀번호로 verify_password → False
  - 만료/무효 JWT 토큰 → InvalidCredentialsError
  - JWT create/decode 왕복 검증 (페이로드 보존)

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**
"""

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.core.exceptions import InvalidCredentialsError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
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

# 비밀번호 전략: bcrypt 72바이트 제한 고려
# null 바이트(\x00) 제외, UTF-8 인코딩 시 72바이트 이하만 허용
_password_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=50,
).filter(lambda p: len(p.encode("utf-8")) <= 72)

# 무효 토큰 전략: JWT 형식이 아닌 랜덤 문자열
_invalid_token_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=100,
).filter(lambda t: "." not in t or len(t.split(".")) != 3)


# ---------------------------------------------------------------------------
# Property: 유효한 access 토큰으로 get_current_user 인증 성공
# 보존 속성: 수정 전후 모두 유효한 access 토큰은 인증에 성공해야 한다
# **Validates: Requirements 3.1**
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(user_data=_user_data_strategy)
@pytest.mark.asyncio
async def test_valid_access_token_authenticates_successfully(user_data: dict):
    """
    보존 속성: 임의의 유효한 사용자 데이터로 생성한 access 토큰을
    get_current_user에 전달하면 해당 사용자가 반환되어야 한다.

    **Validates: Requirements 3.1**
    """
    # access 토큰 생성 (type="access" 포함)
    access_token = create_access_token(user_data)

    # 토큰 디코딩하여 type 필드 확인
    payload = decode_token(access_token)
    assert payload["type"] == "access", "생성된 토큰이 access 타입이어야 한다"

    # get_current_user 의존성 테스트
    from app.core.dependencies import get_current_user

    # DB 세션과 사용자 조회를 모킹
    mock_user = MagicMock()
    mock_user.id = uuid.UUID(user_data["sub"])
    mock_user.email = user_data["email"]

    mock_db = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = mock_user

    with patch("app.core.dependencies.UserRepository", return_value=mock_repo):
        # access 토큰으로 get_current_user 호출 시 사용자 반환
        result = await get_current_user(token=access_token, db=mock_db)
        assert result.id == uuid.UUID(user_data["sub"]), "반환된 사용자 ID가 일치해야 한다"
        assert result.email == user_data["email"], "반환된 사용자 이메일이 일치해야 한다"


# ---------------------------------------------------------------------------
# Property: 올바른 비밀번호로 verify_password → True
# 보존 속성: hash_password로 해싱한 비밀번호는 verify_password로 검증 시 True
# **Validates: Requirements 3.3**
# ---------------------------------------------------------------------------

@settings(max_examples=5, deadline=None)
@given(password=_password_strategy)
def test_verify_password_correct_returns_true(password: str):
    """
    보존 속성: 임의의 비밀번호를 hash_password로 해싱한 후
    동일한 비밀번호로 verify_password를 호출하면 True를 반환해야 한다.

    **Validates: Requirements 3.3**
    """
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True, \
        f"올바른 비밀번호로 검증 시 True여야 한다"


# ---------------------------------------------------------------------------
# Property: 잘못된 비밀번호로 verify_password → False
# 보존 속성: 다른 비밀번호로 검증 시 False 반환
# **Validates: Requirements 3.4**
# ---------------------------------------------------------------------------

@settings(max_examples=5, deadline=None)
@given(
    password=_password_strategy,
    wrong_password=_password_strategy,
)
def test_verify_password_wrong_returns_false(password: str, wrong_password: str):
    """
    보존 속성: 임의의 비밀번호를 hash_password로 해싱한 후
    다른 비밀번호로 verify_password를 호출하면 False를 반환해야 한다.

    **Validates: Requirements 3.4**
    """
    # 두 비밀번호가 같으면 테스트 의미 없음
    assume(password != wrong_password)

    hashed = hash_password(password)
    assert verify_password(wrong_password, hashed) is False, \
        "잘못된 비밀번호로 검증 시 False여야 한다"


# ---------------------------------------------------------------------------
# Property: 만료된 JWT 토큰 → InvalidCredentialsError
# 보존 속성: 만료된 토큰은 디코딩 시 InvalidCredentialsError 발생
# **Validates: Requirements 3.8**
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    user_data=_user_data_strategy,
    seconds_ago=st.integers(min_value=1, max_value=3600),
)
def test_expired_token_raises_invalid_credentials(user_data: dict, seconds_ago: int):
    """
    보존 속성: 만료된 access 토큰을 decode_token에 전달하면
    InvalidCredentialsError가 발생해야 한다.

    **Validates: Requirements 3.8**
    """
    # 이미 만료된 토큰 생성 (음수 timedelta)
    expired_token = create_access_token(
        user_data,
        expires_delta=timedelta(seconds=-seconds_ago),
    )

    with pytest.raises(InvalidCredentialsError):
        decode_token(expired_token)


# ---------------------------------------------------------------------------
# Property: 무효 JWT 토큰 → InvalidCredentialsError
# 보존 속성: 형식이 잘못된 토큰은 디코딩 시 InvalidCredentialsError 발생
# **Validates: Requirements 3.8**
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(invalid_token=_invalid_token_strategy)
def test_invalid_token_raises_invalid_credentials(invalid_token: str):
    """
    보존 속성: 유효하지 않은 형식의 토큰을 decode_token에 전달하면
    InvalidCredentialsError가 발생해야 한다.

    **Validates: Requirements 3.8**
    """
    with pytest.raises(InvalidCredentialsError):
        decode_token(invalid_token)


# ---------------------------------------------------------------------------
# Property: JWT create/decode 왕복 검증 (access 토큰)
# 보존 속성: create_access_token으로 생성한 토큰을 decode_token으로 디코딩하면
#           원본 페이로드(sub, email, auth_provider, type)가 보존되어야 한다
# **Validates: Requirements 3.1**
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(user_data=_user_data_strategy)
def test_jwt_access_token_roundtrip(user_data: dict):
    """
    보존 속성: 임의의 사용자 데이터로 access 토큰을 생성하고
    decode_token으로 디코딩하면 원본 데이터가 보존되어야 한다.

    **Validates: Requirements 3.1**
    """
    token = create_access_token(user_data)
    payload = decode_token(token)

    # 원본 데이터 보존 확인
    assert payload["sub"] == user_data["sub"], "sub 필드가 보존되어야 한다"
    assert payload["email"] == user_data["email"], "email 필드가 보존되어야 한다"
    assert payload["auth_provider"] == user_data["auth_provider"], \
        "auth_provider 필드가 보존되어야 한다"
    assert payload["type"] == "access", "type 필드가 'access'여야 한다"
    # iat, exp 필드 존재 확인
    assert "iat" in payload, "iat 필드가 존재해야 한다"
    assert "exp" in payload, "exp 필드가 존재해야 한다"


# ---------------------------------------------------------------------------
# Property: JWT create/decode 왕복 검증 (refresh 토큰)
# 보존 속성: create_refresh_token으로 생성한 토큰을 decode_token으로 디코딩하면
#           원본 페이로드(sub, email, auth_provider, type)가 보존되어야 한다
# **Validates: Requirements 3.2**
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(user_data=_user_data_strategy)
def test_jwt_refresh_token_roundtrip(user_data: dict):
    """
    보존 속성: 임의의 사용자 데이터로 refresh 토큰을 생성하고
    decode_token으로 디코딩하면 원본 데이터가 보존되어야 한다.

    **Validates: Requirements 3.2**
    """
    token = create_refresh_token(user_data)
    payload = decode_token(token)

    # 원본 데이터 보존 확인
    assert payload["sub"] == user_data["sub"], "sub 필드가 보존되어야 한다"
    assert payload["email"] == user_data["email"], "email 필드가 보존되어야 한다"
    assert payload["auth_provider"] == user_data["auth_provider"], \
        "auth_provider 필드가 보존되어야 한다"
    assert payload["type"] == "refresh", "type 필드가 'refresh'여야 한다"
    # iat, exp 필드 존재 확인
    assert "iat" in payload, "iat 필드가 존재해야 한다"
    assert "exp" in payload, "exp 필드가 존재해야 한다"
