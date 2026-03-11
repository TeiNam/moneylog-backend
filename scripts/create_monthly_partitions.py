#!/usr/bin/env python3
"""
월별 파티션 자동 생성 스크립트.

ledger.ai_chat_messages, ledger.ai_chat_sessions 테이블에 대해
현재 월 기준으로 향후 N개월분 파티션을 미리 생성한다.
이미 존재하는 파티션은 IF NOT EXISTS로 건너뛴다.

사용법:
    # 기본값: 향후 3개월분 파티션 생성
    python scripts/create_monthly_partitions.py

    # 향후 6개월분 파티션 생성
    python scripts/create_monthly_partitions.py --months 6

    # 특정 DATABASE_URL 사용
    DATABASE_URL=postgresql+asyncpg://user:pass@host/db python scripts/create_monthly_partitions.py

환경 변수:
    DATABASE_URL: PostgreSQL 연결 URL (필수)
                  asyncpg 드라이버 URL도 자동으로 psycopg2 동기 드라이버로 변환

cron 설정 예시 (매월 1일 자정에 실행):
    0 0 1 * * cd /path/to/project && python scripts/create_monthly_partitions.py --months 3
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

from sqlalchemy import create_engine, text

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 파티션 대상 테이블 목록 (스키마.테이블명)
PARTITION_TABLES: list[str] = [
    "ledger.ai_chat_messages",
    "ledger.ai_chat_sessions",
]


def _get_sync_database_url() -> str:
    """
    환경 변수에서 DATABASE_URL을 읽고 동기 드라이버 URL로 변환한다.

    프로젝트의 DATABASE_URL은 asyncpg 드라이버를 사용하므로,
    이 스크립트에서는 psycopg2 동기 드라이버로 변환하여 사용한다.
    """
    raw_url = os.environ.get("DATABASE_URL", "")
    if not raw_url:
        logger.error("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)

    # asyncpg → psycopg2 동기 드라이버로 변환
    sync_url = raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    # 순수 postgresql:// 스킴도 지원
    if sync_url.startswith("postgresql://"):
        sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return sync_url


def _build_partition_sql(
    table: str,
    year: int,
    month: int,
) -> str:
    """
    월별 파티션 생성 SQL을 반환한다.

    파티션 이름 규칙: {테이블명}_{YYYY}_{MM}
    범위: [해당 월 1일, 다음 월 1일)

    Args:
        table: 스키마 포함 테이블명 (예: ledger.ai_chat_messages)
        year: 파티션 연도
        month: 파티션 월

    Returns:
        CREATE TABLE IF NOT EXISTS ... PARTITION OF ... SQL 문자열
    """
    # 스키마와 테이블명 분리
    schema, table_name = table.split(".")

    # 파티션 이름: {스키마}.{테이블명}_{YYYY}_{MM}
    partition_name = f"{schema}.{table_name}_{year:04d}_{month:02d}"

    # 시작일: 해당 월 1일
    start_date = date(year, month, 1)

    # 종료일: 다음 월 1일
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    return (
        f"CREATE TABLE IF NOT EXISTS {partition_name}\n"
        f"    PARTITION OF {table}\n"
        f"    FOR VALUES FROM ('{start_date.isoformat()}') "
        f"TO ('{end_date.isoformat()}')"
    )


def create_partitions(months_ahead: int = 3) -> None:
    """
    현재 월 기준으로 향후 N개월분 파티션을 생성한다.

    Args:
        months_ahead: 향후 생성할 파티션 개월 수 (기본값: 3)
    """
    sync_url = _get_sync_database_url()
    engine = create_engine(sync_url)

    today = date.today()
    logger.info(
        "파티션 자동 생성 시작: 기준일=%s, 향후 %d개월",
        today.isoformat(),
        months_ahead,
    )

    # 현재 월부터 향후 N개월까지의 (year, month) 목록 생성
    targets: list[tuple[int, int]] = []
    current = date(today.year, today.month, 1)
    for _ in range(months_ahead + 1):  # 현재 월 포함
        targets.append((current.year, current.month))
        # 다음 월로 이동
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    created_count = 0

    with engine.begin() as conn:
        for table in PARTITION_TABLES:
            for year, month in targets:
                sql = _build_partition_sql(table, year, month)
                logger.info(
                    "파티션 생성: %s_%04d_%02d",
                    table,
                    year,
                    month,
                )
                conn.execute(text(sql))
                created_count += 1

    logger.info(
        "파티션 자동 생성 완료: 총 %d개 파티션 처리 (이미 존재하는 파티션은 건너뜀)",
        created_count,
    )
    engine.dispose()


def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="월별 파티션 자동 생성 스크립트",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="향후 생성할 파티션 개월 수 (기본값: 3)",
    )
    args = parser.parse_args()

    if args.months < 1:
        logger.error("--months 값은 1 이상이어야 합니다: %d", args.months)
        sys.exit(1)

    create_partitions(months_ahead=args.months)


if __name__ == "__main__":
    main()
