"""부분 인덱스 생성: idx_transactions_user_id_date_not_private

transactions 테이블에 공개 거래(is_private = false) 조회 최적화를 위한
부분 인덱스(partial index)를 생성한다.
user_id, date 컬럼에 대해 is_private = false 조건의 부분 인덱스를 추가하여
가족 그룹 통계, 공개 거래 목록 등의 조회 성능을 개선한다.

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op

# Alembic 리비전 식별자
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 부분 인덱스 정보
INDEX_NAME = "idx_transactions_user_id_date_not_private"
TABLE_SCHEMA = "ledger"
TABLE_NAME = "transactions"


def upgrade() -> None:
    """공개 거래 조회용 부분 인덱스를 생성한다."""
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} "
        f"ON {TABLE_SCHEMA}.{TABLE_NAME} (user_id, date) "
        f"WHERE is_private = false"
    )


def downgrade() -> None:
    """부분 인덱스를 삭제한다."""
    op.execute(
        f"DROP INDEX IF EXISTS {TABLE_SCHEMA}.{INDEX_NAME}"
    )
