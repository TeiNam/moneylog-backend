"""인덱스 네이밍 규칙 통일: ALTER INDEX ... RENAME TO ...

모든 인덱스 이름을 `idx_{테이블명}_{컬럼명}` / `uidx_{테이블명}_{컬럼명}` 규칙으로 변경한다.
인덱스 재생성 없이 이름만 변경하므로 테이블 잠금이 발생하지 않는다.

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op

# Alembic 리비전 식별자
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 인덱스 이름 매핑: (이전 이름, 새 이름)
# 설계 문서의 인덱스 네이밍 규칙에 따라 변경
INDEX_RENAME_MAP: list[tuple[str, str]] = [
    # ── transactions 테이블 ──
    ("idx_transaction_user_date", "idx_transactions_user_id_date"),
    ("idx_transaction_family_date", "idx_transactions_family_group_id_date"),
    ("idx_transaction_asset_date", "idx_transactions_asset_id_date"),
    ("idx_transaction_area_date", "idx_transactions_area_date"),
    ("idx_transaction_user_private", "idx_transactions_user_id_is_private"),
    # ── ai_chat_messages 테이블 ──
    ("idx_chat_message_session_created", "idx_ai_chat_messages_session_id_created_at"),
    # ── ai_chat_sessions 테이블 ──
    ("idx_chat_session_user_created", "idx_ai_chat_sessions_user_id_created_at"),
    # ── assets 테이블 ──
    ("idx_asset_user", "idx_assets_user_id"),
    ("idx_asset_family", "idx_assets_family_group_id"),
    # ── subscriptions 테이블 ──
    ("idx_subscription_user", "idx_subscriptions_user_id"),
    ("idx_subscription_user_status", "idx_subscriptions_user_id_status"),
    # ── budgets 테이블 ──
    ("idx_budget_user_year_month", "idx_budgets_user_id_year_month"),
    # ── goals 테이블 ──
    ("idx_goal_user_status", "idx_goals_user_id_status"),
    # ── notifications 테이블 ──
    ("idx_notification_user_read", "idx_notifications_user_id_is_read"),
    # ── receipt_scans 테이블 ──
    ("idx_receipt_scan_user_created", "idx_receipt_scans_user_id_created_at"),
    # ── ai_feedbacks 테이블 ──
    ("idx_ai_feedback_user_created", "idx_ai_feedbacks_user_id_created_at"),
    ("idx_ai_feedback_transaction", "idx_ai_feedbacks_transaction_id"),
    # ── category_configs 테이블 ──
    ("idx_category_owner_area_type", "idx_category_configs_owner_id_owner_type_area_type"),
]


def upgrade() -> None:
    """모든 인덱스 이름을 새 네이밍 규칙으로 변경한다."""
    for old_name, new_name in INDEX_RENAME_MAP:
        op.execute(
            f"ALTER INDEX IF EXISTS ledger.{old_name} RENAME TO {new_name}"
        )


def downgrade() -> None:
    """인덱스 이름을 원래 이름으로 복원한다."""
    for old_name, new_name in INDEX_RENAME_MAP:
        op.execute(
            f"ALTER INDEX IF EXISTS ledger.{new_name} RENAME TO {old_name}"
        )
