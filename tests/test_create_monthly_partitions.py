"""
파티션 자동 생성 스크립트 단위 테스트.

_build_partition_sql, _get_sync_database_url 등 핵심 로직을 검증한다.
DB 연결 없이 SQL 생성 로직과 URL 변환 로직만 테스트한다.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from scripts.create_monthly_partitions import (
    PARTITION_TABLES,
    _build_partition_sql,
    _get_sync_database_url,
)


class TestBuildPartitionSql:
    """_build_partition_sql 함수의 SQL 생성 로직을 검증한다."""

    def test_normal_month(self) -> None:
        """일반 월(1~11월)에 대해 올바른 SQL을 생성하는지 확인한다."""
        sql = _build_partition_sql("ledger.ai_chat_messages", 2026, 3)

        assert "CREATE TABLE IF NOT EXISTS ledger.ai_chat_messages_2026_03" in sql
        assert "PARTITION OF ledger.ai_chat_messages" in sql
        assert "FOR VALUES FROM ('2026-03-01') TO ('2026-04-01')" in sql

    def test_december_to_january(self) -> None:
        """12월 파티션의 종료일이 다음 해 1월 1일인지 확인한다."""
        sql = _build_partition_sql("ledger.ai_chat_sessions", 2025, 12)

        assert "ledger.ai_chat_sessions_2025_12" in sql
        assert "FOR VALUES FROM ('2025-12-01') TO ('2026-01-01')" in sql

    def test_january(self) -> None:
        """1월 파티션이 올바르게 생성되는지 확인한다."""
        sql = _build_partition_sql("ledger.ai_chat_messages", 2026, 1)

        assert "ledger.ai_chat_messages_2026_01" in sql
        assert "FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')" in sql

    def test_partition_name_zero_padded(self) -> None:
        """월이 한 자리일 때 0으로 패딩되는지 확인한다."""
        sql = _build_partition_sql("ledger.ai_chat_messages", 2026, 5)

        assert "ai_chat_messages_2026_05" in sql

    def test_both_target_tables(self) -> None:
        """PARTITION_TABLES에 정의된 두 테이블 모두 SQL 생성이 가능한지 확인한다."""
        for table in PARTITION_TABLES:
            sql = _build_partition_sql(table, 2026, 6)
            schema, table_name = table.split(".")
            assert f"{schema}.{table_name}_2026_06" in sql
            assert f"PARTITION OF {table}" in sql


class TestGetSyncDatabaseUrl:
    """_get_sync_database_url 함수의 URL 변환 로직을 검증한다."""

    def test_asyncpg_to_psycopg2(self) -> None:
        """asyncpg 드라이버 URL이 psycopg2로 변환되는지 확인한다."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db"},
        ):
            result = _get_sync_database_url()
            assert result == "postgresql+psycopg2://user:pass@localhost/db"

    def test_plain_postgresql_to_psycopg2(self) -> None:
        """순수 postgresql:// URL이 psycopg2로 변환되는지 확인한다."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@localhost/db"},
        ):
            result = _get_sync_database_url()
            assert result == "postgresql+psycopg2://user:pass@localhost/db"

    def test_missing_database_url_exits(self) -> None:
        """DATABASE_URL이 없으면 sys.exit(1)이 호출되는지 확인한다."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                _get_sync_database_url()
            assert exc_info.value.code == 1

    def test_already_psycopg2_unchanged(self) -> None:
        """이미 psycopg2 드라이버인 URL은 그대로 유지되는지 확인한다."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql+psycopg2://user:pass@localhost/db"},
        ):
            result = _get_sync_database_url()
            assert result == "postgresql+psycopg2://user:pass@localhost/db"
