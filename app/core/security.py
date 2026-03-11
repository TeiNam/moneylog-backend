"""
보안 모듈 — 비밀번호 해싱 및 JWT 토큰 관리.

비밀번호: bcrypt 라이브러리 직접 사용 (passlib 호환성 이슈로 인해)
JWT: python-jose 라이브러리 (HS256 알고리즘)
"""

import logging
import re
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidCredentialsError

logger = logging.getLogger(__name__)

# 비밀번호 규칙: 영문 1개 이상, 숫자 1개 이상
_RE_HAS_LETTER = re.compile(r"[a-zA-Z]")
_RE_HAS_DIGIT = re.compile(r"\d")


# ---------------------------------------------------------------------------
# 비밀번호 해싱
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """비밀번호를 bcrypt로 해싱하여 반환한다."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """평문 비밀번호와 해시를 비교하여 일치 여부를 반환한다."""
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            hashed.encode("utf-8"),
        )
    except Exception:
        logger.warning("비밀번호 검증 중 오류 발생")
        return False


def validate_password(password: str) -> bool:
    """
    비밀번호 규칙을 검증한다.

    규칙:
      - 8자 이상
      - 영문자 1개 이상 포함
      - 숫자 1개 이상 포함
    """
    if len(password) < 8:
        return False
    if not _RE_HAS_LETTER.search(password):
        return False
    if not _RE_HAS_DIGIT.search(password):
        return False
    return True


# ---------------------------------------------------------------------------
# JWT 토큰
# ---------------------------------------------------------------------------

def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """
    JWT 액세스 토큰을 생성한다.

    Args:
        data: 페이로드에 포함할 데이터 (sub, email, auth_provider 등)
        expires_delta: 만료 시간 간격. None이면 설정의 기본값(30분) 사용.

    Returns:
        인코딩된 JWT 문자열
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        **data,
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(data: dict) -> str:
    """
    JWT 리프레시 토큰을 생성한다 (7일 만료).

    Args:
        data: 페이로드에 포함할 데이터 (sub, email, auth_provider 등)

    Returns:
        인코딩된 JWT 문자열
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        **data,
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """
    JWT 토큰을 디코딩하여 페이로드를 반환한다.

    Args:
        token: 인코딩된 JWT 문자열

    Returns:
        디코딩된 페이로드 딕셔너리

    Raises:
        InvalidCredentialsError: 토큰이 만료되었거나 유효하지 않은 경우
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        logger.warning("JWT 디코딩 실패: %s", exc)
        raise InvalidCredentialsError(detail="유효하지 않은 토큰입니다") from exc
