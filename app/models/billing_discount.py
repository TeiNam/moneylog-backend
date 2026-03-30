"""
BillingDiscount SQLAlchemy 모델.

ledger 스키마에 속하는 카드 청구할인 항목 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from datetime import date as date_type
from uuid import UUID

from sqlalchemy import DATE, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class BillingDiscount(Base):
    """청구할인 모델 (ledger.billing_discounts 테이블)."""

    __tablename__ = "billing_discounts"
    __table_args__ = (
        Index("idx_billing_discounts_asset_id", "asset_id"),
        Index("idx_billing_discounts_cycle", "asset_id", "cycle_start", "cycle_end"),
        {"schema": "ledger", "comment": "카드 청구할인 항목 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: ledger.assets.id (FK 제약 없음)
    asset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → ledger.assets.id",
    )
    # 논리적 FK: auth.users.id (FK 제약 없음)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="할인명",
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="할인 금액 (0 이상)",
    )
    cycle_start: Mapped[date_type] = mapped_column(
        DATE, nullable=False, comment="적용 결제 주기 시작일",
    )
    cycle_end: Mapped[date_type] = mapped_column(
        DATE, nullable=False, comment="적용 결제 주기 종료일",
    )
    memo: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="메모",
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
