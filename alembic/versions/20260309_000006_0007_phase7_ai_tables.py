"""Phase 7 AI 연동 테이블 생성

ledger.ai_chat_sessions, ledger.ai_chat_messages,
ledger.receipt_scans, ledger.ai_feedbacks 테이블을 생성한다.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic 리비전 식별자
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ledger 스키마가 없으면 생성 (이전 Phase에서 이미 생성했지만 안전을 위해 포함)
    op.execute("CREATE SCHEMA IF NOT EXISTS ledger")

    # ── ledger.ai_chat_sessions 테이블 생성 ──
    op.create_table(
        "ai_chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="AI 채팅 세션 테이블",
    )

    # ai_chat_sessions 인덱스: (user_id, created_at)
    op.create_index(
        "idx_chat_session_user_created",
        "ai_chat_sessions",
        ["user_id", "created_at"],
        schema="ledger",
    )

    # ── ledger.ai_chat_messages 테이블 생성 ──
    op.create_table(
        "ai_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("extracted_data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="AI 채팅 메시지 테이블",
    )

    # ai_chat_messages 인덱스: (session_id, created_at)
    op.create_index(
        "idx_chat_message_session_created",
        "ai_chat_messages",
        ["session_id", "created_at"],
        schema="ledger",
    )

    # ── ledger.receipt_scans 테이블 생성 ──
    op.create_table(
        "receipt_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extracted_data", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="영수증 OCR 스캔 테이블",
    )

    # receipt_scans 인덱스: (user_id, created_at)
    op.create_index(
        "idx_receipt_scan_user_created",
        "receipt_scans",
        ["user_id", "created_at"],
        schema="ledger",
    )

    # ── ledger.ai_feedbacks 테이블 생성 ──
    op.create_table(
        "ai_feedbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feedback_type", sa.String(30), nullable=False),
        sa.Column("original_value", sa.String(200), nullable=False),
        sa.Column("corrected_value", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="ledger",
        comment="AI 오분류 피드백 테이블",
    )

    # ai_feedbacks 인덱스: (user_id, created_at)
    op.create_index(
        "idx_ai_feedback_user_created",
        "ai_feedbacks",
        ["user_id", "created_at"],
        schema="ledger",
    )

    # ai_feedbacks 인덱스: (transaction_id)
    op.create_index(
        "idx_ai_feedback_transaction",
        "ai_feedbacks",
        ["transaction_id"],
        schema="ledger",
    )


def downgrade() -> None:
    # 역순으로 테이블 삭제: ai_feedbacks → receipt_scans → ai_chat_messages → ai_chat_sessions
    op.drop_table("ai_feedbacks", schema="ledger")
    op.drop_table("receipt_scans", schema="ledger")
    op.drop_table("ai_chat_messages", schema="ledger")
    op.drop_table("ai_chat_sessions", schema="ledger")
