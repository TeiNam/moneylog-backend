"""
Alembic 환경 설정 파일.

async 엔진 호환 설정으로, SQLAlchemy 모델 autogenerate를 지원한다.
멀티 스키마(auth, ledger, stats) 마이그레이션을 위해 include_schemas=True 설정.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models.base import Base
import app.models  # noqa: F401 — autogenerate용 전체 모델 등록 (Phase 1-7)

# Alembic Config 객체 (alembic.ini 값 접근)
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate를 위한 메타데이터 설정
target_metadata = Base.metadata

# alembic_version 테이블을 auth 스키마에 배치
version_table_schema = "auth"

# 설정에서 DATABASE_URL 동적 로드
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def include_name(name, type_, parent_names):
    """멀티 스키마 마이그레이션에서 대상 스키마만 포함한다."""
    if type_ == "schema":
        return name in ("auth", "ledger", "stats")
    return True


def run_migrations_offline() -> None:
    """오프라인 모드에서 마이그레이션 실행 (SQL 스크립트 생성)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema=version_table_schema,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """마이그레이션 실행 (동기 컨텍스트)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema=version_table_schema,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """async 엔진으로 마이그레이션을 실행한다."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """온라인 모드에서 비동기 마이그레이션 실행."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
