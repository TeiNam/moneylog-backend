"""
SQLAlchemy 2.0 async 기반 PostgreSQL 연결 관리 모듈.

AsyncEngine과 세션 팩토리를 lazy하게 생성하고,
요청별 세션 생성/정리를 위한 비동기 제너레이터를 제공한다.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class _DatabaseManager:
    """데이터베이스 엔진과 세션 팩토리의 싱글턴 관리자.

    global 키워드 대신 인스턴스 변수로 상태를 캡슐화한다.
    """

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def get_engine(self) -> AsyncEngine:
        """AsyncEngine 싱글턴을 반환한다 (lazy 초기화)."""
        if self._engine is None:
            settings = get_settings()
            self._engine = create_async_engine(
                settings.DATABASE_URL,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=settings.DEBUG,
            )
            logger.info("AsyncEngine 생성 완료: %s", settings.DATABASE_URL[:30] + "...")
        return self._engine

    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """async_sessionmaker 싱글턴을 반환한다 (lazy 초기화)."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._session_factory


# 모듈 수준 싱글턴 인스턴스
_db_manager = _DatabaseManager()


# 기존 공개 인터페이스 유지 (하위 호환)
def get_engine() -> AsyncEngine:
    """AsyncEngine 싱글턴을 반환한다 (lazy 초기화)."""
    return _db_manager.get_engine()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """async_sessionmaker 싱글턴을 반환한다 (lazy 초기화)."""
    return _db_manager.get_session_factory()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    요청별 비동기 세션을 생성하고 정리하는 제너레이터.

    FastAPI 의존성 주입에서 사용되며,
    요청 처리 완료 후 세션을 자동으로 닫는다.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """
    데이터베이스 연결 상태를 확인한다.

    SELECT 1 쿼리를 실행하여 연결이 정상인지 검증한다.

    Returns:
        True: 연결 정상
        False: 연결 실패
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("데이터베이스 연결 확인 실패")
        return False
