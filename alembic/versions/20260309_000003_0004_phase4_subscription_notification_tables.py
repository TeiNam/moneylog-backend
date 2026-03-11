"""Phase 4 구독 및 알림 테이블 생성

ledger.subscriptions, ledger.notifications 테이블을 생성한다.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic 리비전 식별자
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ledger 스키마가 없으면 생성 (이전 Phase에서 이미 생성했지만 안전을 위해 포함)
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")

    # ── ledger.subscriptions 테이블 생성 ──
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("cycle", sa.String(20), nullable=False),
        sa.Column("billing_day", sa.Integer(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("start_date", sa.DATE(), nullable=False),
        sa.Column("end_date", sa.DATE(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "notify_before_days",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="구독 관리 테이블",
    )

    # subscriptions 인덱스
    op.create_index(
        "idx_subscription_user",
        "subscriptions",
        ["user_id"],
        schema="ledger",
    )
    op.create_index(
        "idx_subscription_user_status",
        "subscriptions",
        ["user_id", "status"],
        schema="ledger",
    )

    # ── ledger.notifications 테이블 생성 ──
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="알림 테이블",
    )

    # notifications 인덱스
    op.create_index(
        "idx_notification_user_read",
        "notifications",
        ["user_id", "is_read"],
        schema="ledger",
    )


def downgrade() -> None:
    # 테이블을 생성 역순으로 삭제 (notifications → subscriptions)
    op.drop_table("notifications", schema="ledger")
    op.drop_table("subscriptions", schema="ledger")
