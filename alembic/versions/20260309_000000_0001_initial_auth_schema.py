"""초기 auth 스키마 및 users, email_verifications 테이블 생성

Revision ID: 0001
Revises:
Create Date: 2026-03-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 스키마 생성
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")
    op.execute("CREATE SCHEMA IF NOT EXISTS stats")

    # auth.users 테이블 생성
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("profile_image", sa.String(500), nullable=True),
        sa.Column("auth_provider", sa.String(20), nullable=False, server_default="EMAIL"),
        sa.Column("family_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role_in_group", sa.String(20), nullable=False, server_default="MEMBER"),
        sa.Column("default_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
        comment="사용자 계정 정보 테이블",
    )

    # auth.users 인덱스
    op.create_index(
        "uidx_users_email",
        "users",
        ["email"],
        unique=True,
        schema="auth",
    )

    # auth.email_verifications 테이블 생성
    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
        comment="이메일 인증 코드 관리 테이블",
    )

    # auth.email_verifications 인덱스
    op.create_index(
        "idx_email_verifications_user_id",
        "email_verifications",
        ["user_id"],
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("email_verifications", schema="auth")
    op.drop_table("users", schema="auth")
    op.execute("DROP SCHEMA IF EXISTS stats")
    op.execute("DROP SCHEMA IF EXISTS ledger")
    op.execute("DROP SCHEMA IF EXISTS auth")
