"""
테스트 픽스처 설정.

테스트용 SQLite async 인메모리 DB, AsyncClient, DB 세션,
테스트 사용자 생성 헬퍼, 이메일 발송 모킹을 제공한다.

주의: SQLite는 PostgreSQL 스키마(auth, ledger, stats)를 지원하지 않으므로,
테이블 생성 전에 모델 메타데이터에서 스키마 정보를 제거한다.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import hash_password
from app.models.base import Base
from app.models.user import EmailVerification, User  # noqa: F401 — 메타데이터 등록용

# Phase 2 모델 등록 (Alembic 메타데이터 인식용)
from app.models.transaction import CarExpenseDetail, CeremonyEvent, Transaction  # noqa: F401
from app.models.ceremony_person import CeremonyPerson  # noqa: F401
from app.models.category_config import CategoryConfig  # noqa: F401

# Phase 3 모델 등록
from app.models.asset import Asset  # noqa: F401
from app.models.family_group import FamilyGroup  # noqa: F401

# Phase 4 모델 등록
from app.models.subscription import Subscription  # noqa: F401
from app.models.notification import Notification  # noqa: F401

# Phase 5 모델 등록
from app.models.budget import Budget  # noqa: F401
from app.models.goal import Goal  # noqa: F401

# Phase 6 모델 등록
from app.models.transfer import Transfer  # noqa: F401

# Phase 7 모델 등록
from app.models.chat_session import ChatSession  # noqa: F401
from app.models.chat_message import ChatMessage  # noqa: F401
from app.models.receipt_scan import ReceiptScan  # noqa: F401
from app.models.ai_feedback import AIFeedback  # noqa: F401

# ---------------------------------------------------------------------------
# 테스트용 SQLite async 인메모리 DB 설정
# ---------------------------------------------------------------------------

# aiosqlite 드라이버를 사용한 인메모리 SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


_metadata_cleaned = False


def _remove_schema_from_metadata() -> None:
    """
    SQLite 호환을 위해 Base.metadata의 모든 테이블에서 schema 정보를 제거하고,
    PostgreSQL 전용 ARRAY 타입을 JSON 직렬화 Text로 변환한다.

    1회 실행 가드를 통해 최초 호출 시에만 실제 변환을 수행한다.
    """
    global _metadata_cleaned
    if _metadata_cleaned:
        return

    import json

    from sqlalchemy import ARRAY, JSON, Text, TypeDecorator
    from sqlalchemy.dialects.postgresql import JSONB

    class JSONEncodedList(TypeDecorator):
        """SQLite용 list ↔ JSON 문자열 변환 타입."""

        impl = Text
        cache_ok = True

        def process_bind_param(self, value, dialect):
            if value is not None:
                return json.dumps(value, ensure_ascii=False)
            return "[]"

        def process_result_value(self, value, dialect):
            if value is not None:
                return json.loads(value)
            return []

    from sqlalchemy import Integer

    for table in Base.metadata.tables.values():
        table.schema = None
        for column in table.columns:
            if isinstance(column.type, ARRAY):
                column.type = JSONEncodedList()
            elif isinstance(column.type, JSONB):
                column.type = JSON()
            # SQLite는 Identity()를 지원하지 않으므로,
            # BigInteger + Identity PK를 Integer로 변환
            if column.identity is not None:
                column.identity = None
                column.type = Integer()
                column.autoincrement = True

    # SQLite는 복합 PK + autoincrement를 지원하지 않으므로,
    # 파티셔닝용 복합 PK 테이블에서 PK를 id 단일 컬럼으로 축소
    from sqlalchemy import PrimaryKeyConstraint

    for table in Base.metadata.tables.values():
        pk = table.primary_key
        pk_col_names = [c.name for c in pk.columns]
        if len(pk_col_names) > 1 and "id" in pk_col_names:
            # 기존 복합 PK 제거 후 id 단일 PK로 재설정
            # (PostgreSQL 파티셔닝 전용 복합 PK는 SQLite에서 불필요)
            for col in pk.columns:
                col.primary_key = False
            table.constraints.discard(pk)
            new_pk = PrimaryKeyConstraint(table.c.id)
            table.append_constraint(new_pk)
            # UUID PK는 autoincrement와 호환되지 않으므로,
            # Integer/BigInteger 계열만 autoincrement 설정
            from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
            from sqlalchemy.types import Uuid
            id_type = table.c.id.type
            is_uuid = isinstance(id_type, (_PG_UUID, Uuid))
            if not is_uuid:
                table.c.id.autoincrement = True

            # 복합 PK에서 제외된 created_at에 Python 기본값 추가
            # (SQLite에서 RETURNING으로 server_default 값을 받지 못하는 문제 방지)
            if "created_at" in table.c:
                from datetime import datetime, timezone
                from sqlalchemy import ColumnDefault
                created_col = table.c.created_at
                if created_col.default is None:
                    default_obj = ColumnDefault(lambda ctx: datetime.now(timezone.utc))
                    default_obj._set_parent_with_dispatch(created_col)

    _metadata_cleaned = True


@pytest.fixture(scope="session")
def _test_engine():
    """세션 범위의 테스트용 async 엔진을 생성한다."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    return engine


@pytest.fixture(scope="session")
def _test_session_factory(_test_engine):
    """세션 범위의 async 세션 팩토리를 생성한다."""
    return async_sessionmaker(
        bind=_test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture(autouse=True)
async def _setup_database(_test_engine):
    """
    각 테스트 전에 테이블을 생성하고, 테스트 후에 삭제한다.

    SQLite는 스키마를 지원하지 않으므로 메타데이터에서 스키마를 제거한 뒤
    create_all / drop_all을 수행한다.
    """
    _remove_schema_from_metadata()

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# 테스트 DB 세션 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_session(_test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    테스트용 AsyncSession을 제공한다.

    각 테스트마다 독립적인 세션을 생성하고,
    테스트 완료 후 커밋하여 데이터를 반영한다.
    """
    async with _test_session_factory() as session:
        yield session
        await session.commit()


# ---------------------------------------------------------------------------
# AsyncClient 픽스처 (httpx)
# ---------------------------------------------------------------------------

@pytest.fixture
async def client(_test_session_factory) -> AsyncGenerator[AsyncClient, None]:
    """
    FastAPI 앱에 대한 비동기 HTTP 클라이언트를 제공한다.

    get_db 의존성을 오버라이드하여 테스트 DB 세션을 주입한다.
    """
    from app.core.dependencies import get_db
    from app.main import app

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with _test_session_factory() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    # 의존성 오버라이드 정리
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 테스트 사용자 생성 헬퍼
# ---------------------------------------------------------------------------

async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "testpass1",
    nickname: str = "테스트유저",
    email_verified: bool = False,
) -> User:
    """
    테스트용 사용자를 생성하여 반환한다.

    Args:
        db: AsyncSession 인스턴스
        email: 이메일 주소
        password: 평문 비밀번호 (bcrypt 해싱 후 저장)
        nickname: 닉네임
        email_verified: 이메일 인증 완료 여부

    Returns:
        생성된 User 인스턴스
    """
    user = User(
        email=email,
        password_hash=hash_password(password),
        nickname=nickname,
        auth_provider="EMAIL",
        status="ACTIVE",
        email_verified=email_verified,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# 이메일 발송 모킹 설정
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_email_sending():
    """
    이메일 발송을 모킹한다.

    Phase 1에서는 실제 SMTP 발송이 없으므로,
    향후 이메일 발송 함수가 추가될 때를 대비한 기본 모킹 설정이다.
    """
    with patch(
        "app.services.auth_service.EmailAuthService._generate_verification_code",
        return_value="123456",
    ):
        yield
