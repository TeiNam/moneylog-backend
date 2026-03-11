"""Phase 3 자산 및 가족 그룹 테이블 생성

auth.family_groups, ledger.assets 테이블을 생성한다.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic 리비전 식별자
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # auth 스키마가 없으면 생성 (Phase 1에서 이미 생성했지만 안전을 위해 포함)
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    # ledger 스키마가 없으면 생성 (Phase 1에서 이미 생성했지만 안전을 위해 포함)
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")

    # ── auth.family_groups 테이블 생성 ──
    op.create_table(
        "family_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("invite_code", sa.String(8), nullable=False),
        sa.Column(
            "invite_code_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
        comment="가족 그룹 테이블",
    )

    # invite_code 유니크 인덱스
    op.create_index(
        "ix_family_groups_invite_code",
        "family_groups",
        ["invite_code"],
        unique=True,
        schema="auth",
    )

    # ── ledger.assets 테이블 생성 ──
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ownership", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("asset_type", sa.String(20), nullable=False),
        sa.Column("institution", sa.String(100), nullable=True),
        sa.Column("balance", sa.BigInteger(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="자산(결제수단) 테이블",
    )

    # assets 인덱스
    op.create_index(
        "idx_asset_user",
        "assets",
        ["user_id"],
        schema="ledger",
    )
    op.create_index(
        "idx_asset_family",
        "assets",
        ["family_group_id"],
        schema="ledger",
    )


def downgrade() -> None:
    # 테이블을 생성 역순으로 삭제
    op.drop_table("assets", schema="ledger")
    op.drop_table("family_groups", schema="auth")
