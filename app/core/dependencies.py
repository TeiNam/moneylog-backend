"""
FastAPI 의존성 주입 함수.

요청별 DB 세션 제공 및 Bearer 토큰 기반 현재 사용자 추출을 담당한다.
"""

import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, InvalidCredentialsError
from app.core.security import decode_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

# Bearer 토큰 추출 스킴
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """요청별 AsyncSession을 제공하고 완료 후 자동 정리한다."""
    async for session in get_async_session():
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Bearer 토큰에서 현재 사용자를 추출한다.

    1. decode_token으로 페이로드 디코딩
    2. sub에서 user_id 추출
    3. UserRepository로 사용자 조회
    4. 없으면 401 Unauthorized

    Raises:
        InvalidCredentialsError: 토큰 무효 또는 사용자 미존재
    """
    # decode_token은 실패 시 InvalidCredentialsError를 발생시킴
    payload = decode_token(token)

    # 토큰 타입 검증: access 토큰만 허용, refresh 등 다른 타입은 거부
    token_type = payload.get("type")
    if token_type != "access":
        raise InvalidCredentialsError(detail="유효하지 않은 토큰입니다")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidCredentialsError(detail="유효하지 않은 토큰입니다")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise InvalidCredentialsError(detail="유효하지 않은 토큰입니다")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise InvalidCredentialsError(detail="유효하지 않은 토큰입니다")

    return user

async def verify_batch_api_key(x_api_key: str = Header(...)) -> None:
    """
    배치 엔드포인트용 API 키 인증 의존성.

    X-API-Key 헤더에서 API 키를 읽어 settings.BATCH_API_KEY와 비교한다.
    헤더 누락 시 FastAPI가 자동으로 422를 반환한다 (Header(...) 사용).

    Raises:
        ForbiddenError: API 키가 일치하지 않을 때
    """
    settings = get_settings()
    if x_api_key != settings.BATCH_API_KEY:
        raise ForbiddenError("배치 실행 권한이 없습니다")

