"""Phase 5 예산 및 목표 테이블 생성

ledger.budgets, ledger.goals 테이블을 생성한다.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic 리비전 식별자
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ledger 스키마가 없으면 생성 (이전 Phase에서 이미 생성했지만 안전을 위해 포함)
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")

    # ── ledger.budgets 테이블 생성 ──
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("budget_amount", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="월별 카테고리별 예산 테이블",
    )

    # budgets 인덱스: (user_id, year, month)
    op.create_index(
        "idx_budget_user_year_month",
        "budgets",
        ["user_id", "year", "month"],
        schema="ledger",
    )

    # ── ledger.goals 테이블 생성 ──
    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("target_amount", sa.Integer(), nullable=False),
        sa.Column(
            "current_amount",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("start_date", sa.DATE(), nullable=False),
        sa.Column("end_date", sa.DATE(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="재무 목표 테이블",
    )

    # goals 인덱스: (user_id, status)
    op.create_index(
        "idx_goal_user_status",
        "goals",
        ["user_id", "status"],
        schema="ledger",
    )


def downgrade() -> None:
    # 테이블을 생성 역순으로 삭제 (goals → budgets)
    op.drop_table("goals", schema="ledger")
    op.drop_table("budgets", schema="ledger")
