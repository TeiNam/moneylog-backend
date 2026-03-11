"""Phase 2 ledger 스키마 테이블 생성

transactions, car_expense_details, ceremony_events,
ceremony_persons, category_configs 테이블을 생성한다.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic 리비전 식별자
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ledger 스키마가 없으면 생성 (Phase 1에서 이미 생성했지만 안전을 위해 포함)
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")

    # ── ledger.transactions 테이블 생성 ──
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("date", sa.DATE(), nullable=False),
        sa.Column("area", sa.String(20), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("major_category", sa.String(50), nullable=False),
        sa.Column("minor_category", sa.String(50), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("discount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_amount", sa.Integer(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="수입/지출 거래 내역 테이블",
    )

    # transactions 복합 인덱스
    op.create_index(
        "idx_transaction_user_date",
        "transactions",
        ["user_id", "date"],
        schema="ledger",
    )
    op.create_index(
        "idx_transaction_family_date",
        "transactions",
        ["family_group_id", "date"],
        schema="ledger",
    )
    op.create_index(
        "idx_transaction_asset_date",
        "transactions",
        ["asset_id", "date"],
        schema="ledger",
    )
    op.create_index(
        "idx_transaction_area_date",
        "transactions",
        ["area", "date"],
        schema="ledger",
    )

    # ── ledger.car_expense_details 테이블 생성 ──
    op.create_table(
        "car_expense_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("car_type", sa.String(20), nullable=False),
        sa.Column("fuel_amount_liter", sa.DECIMAL(), nullable=True),
        sa.Column("fuel_unit_price", sa.Integer(), nullable=True),
        sa.Column("odometer", sa.Integer(), nullable=True),
        sa.Column("station_name", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="차계부 비용 상세 테이블",
    )

    # ── ledger.ceremony_events 테이블 생성 ──
    op.create_table(
        "ceremony_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("person_name", sa.String(50), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("venue", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="경조사 이벤트 상세 테이블",
    )

    # ── ledger.ceremony_persons 테이블 생성 ──
    op.create_table(
        "ceremony_persons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("total_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="경조사 인물 누적 기록 테이블",
    )

    # ── ledger.category_configs 테이블 생성 ──
    op.create_table(
        "category_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_type", sa.String(20), nullable=False),
        sa.Column("area", sa.String(20), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("major_category", sa.String(50), nullable=False),
        sa.Column(
            "minor_categories",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
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
        comment="카테고리 설정 테이블",
    )

    # category_configs 복합 인덱스
    op.create_index(
        "idx_category_owner_area_type",
        "category_configs",
        ["owner_id", "owner_type", "area", "type"],
        schema="ledger",
    )


def downgrade() -> None:
    # 테이블을 생성 역순으로 삭제
    op.drop_table("category_configs", schema="ledger")
    op.drop_table("ceremony_persons", schema="ledger")
    op.drop_table("ceremony_events", schema="ledger")
    op.drop_table("car_expense_details", schema="ledger")
    op.drop_table("transactions", schema="ledger")
    # ledger 스키마는 Phase 1에서 생성했으므로 여기서 DROP하지 않음
