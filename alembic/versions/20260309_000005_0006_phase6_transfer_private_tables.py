"""Phase 6 이체 테이블 생성 및 비밀 모드 컬럼 추가

ledger.transfers 테이블을 생성하고,
ledger.transactions 테이블에 is_private 컬럼을 추가한다.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic 리비전 식별자
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ledger 스키마가 없으면 생성 (이전 Phase에서 이미 생성했지만 안전을 위해 포함)
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")

    # ── ledger.transfers 테이블 생성 ──
    op.create_table(
        "transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("fee", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("transfer_date", sa.DATE(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="계좌 간 이체 내역 테이블",
    )

    # transfers 인덱스: (user_id, transfer_date)
    op.create_index(
        "idx_transfer_user_date",
        "transfers",
        ["user_id", "transfer_date"],
        schema="ledger",
    )

    # ── ledger.transactions 테이블에 is_private 컬럼 추가 ──
    op.add_column(
        "transactions",
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        schema="ledger",
    )

    # transactions 인덱스: (user_id, is_private)
    op.create_index(
        "idx_transaction_user_private",
        "transactions",
        ["user_id", "is_private"],
        schema="ledger",
    )


def downgrade() -> None:
    # 역순으로 삭제: 인덱스 → 컬럼 → 테이블
    op.drop_index(
        "idx_transaction_user_private",
        table_name="transactions",
        schema="ledger",
    )
    op.drop_column("transactions", "is_private", schema="ledger")
    op.drop_table("transfers", schema="ledger")
