"""논리적 FK 컬럼에 COMMENT ON COLUMN 추가

모든 논리적 FK 컬럼에 대해 DB 레벨의 COMMENT ON COLUMN을 설정하여
데이터베이스 스키마만으로도 테이블 간 관계를 파악할 수 있게 한다.
모델에 정의된 comment 파라미터와 DB 주석을 동기화한다.

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-11

"""

from typing import Sequence, Union

from alembic import op

# Alembic 리비전 식별자
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 논리적 FK 컬럼 목록: (스키마, 테이블, 컬럼, 주석)
# 모델에 정의된 comment 파라미터와 동일한 값을 DB에 반영한다.
LOGICAL_FK_COMMENTS: list[tuple[str, str, str, str]] = [
    # ── auth.users ──
    (
        "auth", "users", "family_group_id",
        "논리적 FK → auth.family_groups.id",
    ),
    (
        "auth", "users", "default_asset_id",
        "논리적 FK → ledger.assets.id",
    ),
    # ── auth.email_verifications ──
    (
        "auth", "email_verifications", "user_id",
        "논리적 FK → auth.users.id",
    ),
    # ── auth.family_groups ──
    (
        "auth", "family_groups", "owner_id",
        "논리적 FK → auth.users.id (그룹장)",
    ),
    # ── ledger.transactions ──
    (
        "ledger", "transactions", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "transactions", "family_group_id",
        "논리적 FK → auth.family_groups.id",
    ),
    (
        "ledger", "transactions", "asset_id",
        "논리적 FK → ledger.assets.id",
    ),
    # ── ledger.car_expense_details ──
    (
        "ledger", "car_expense_details", "transaction_id",
        "논리적 FK → ledger.transactions.id",
    ),
    # ── ledger.ceremony_events ──
    (
        "ledger", "ceremony_events", "transaction_id",
        "논리적 FK → ledger.transactions.id",
    ),
    # ── ledger.transfers ──
    (
        "ledger", "transfers", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "transfers", "family_group_id",
        "논리적 FK → auth.family_groups.id",
    ),
    (
        "ledger", "transfers", "from_asset_id",
        "논리적 FK → ledger.assets.id (출금 자산)",
    ),
    (
        "ledger", "transfers", "to_asset_id",
        "논리적 FK → ledger.assets.id (입금 자산)",
    ),
    # ── ledger.assets ──
    (
        "ledger", "assets", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "assets", "family_group_id",
        "논리적 FK → auth.family_groups.id",
    ),
    # ── ledger.subscriptions ──
    (
        "ledger", "subscriptions", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "subscriptions", "family_group_id",
        "논리적 FK → auth.family_groups.id",
    ),
    (
        "ledger", "subscriptions", "asset_id",
        "논리적 FK → ledger.assets.id",
    ),
    # ── ledger.budgets ──
    (
        "ledger", "budgets", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "budgets", "family_group_id",
        "논리적 FK → auth.family_groups.id",
    ),
    # ── ledger.goals ──
    (
        "ledger", "goals", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "goals", "family_group_id",
        "논리적 FK → auth.family_groups.id",
    ),
    # ── ledger.notifications ──
    (
        "ledger", "notifications", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "notifications", "subscription_id",
        "논리적 FK → ledger.subscriptions.id",
    ),
    # ── ledger.receipt_scans ──
    (
        "ledger", "receipt_scans", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "receipt_scans", "transaction_id",
        "논리적 FK → ledger.transactions.id",
    ),
    # ── ledger.ai_chat_sessions ──
    (
        "ledger", "ai_chat_sessions", "user_id",
        "논리적 FK → auth.users.id",
    ),
    # ── ledger.ai_chat_messages ──
    (
        "ledger", "ai_chat_messages", "session_id",
        "논리적 FK → ledger.ai_chat_sessions.id",
    ),
    # ── ledger.ai_feedbacks ──
    (
        "ledger", "ai_feedbacks", "user_id",
        "논리적 FK → auth.users.id",
    ),
    (
        "ledger", "ai_feedbacks", "transaction_id",
        "논리적 FK → ledger.transactions.id",
    ),
    # ── ledger.category_configs ──
    (
        "ledger", "category_configs", "owner_id",
        "논리적 FK → auth.users.id (owner_type=FAMILY_GROUP일 때 auth.family_groups.id)",
    ),
    # ── ledger.ceremony_persons ──
    (
        "ledger", "ceremony_persons", "user_id",
        "논리적 FK → auth.users.id",
    ),
]


def upgrade() -> None:
    """모든 논리적 FK 컬럼에 COMMENT ON COLUMN을 설정한다."""
    for schema, table, column, comment_text in LOGICAL_FK_COMMENTS:
        # 작은따옴표 이스케이프 처리
        escaped = comment_text.replace("'", "''")
        op.execute(
            f"COMMENT ON COLUMN {schema}.{table}.{column} IS '{escaped}'"
        )


def downgrade() -> None:
    """모든 논리적 FK 컬럼의 COMMENT를 제거한다."""
    for schema, table, column, _ in LOGICAL_FK_COMMENTS:
        op.execute(
            f"COMMENT ON COLUMN {schema}.{table}.{column} IS NULL"
        )
