"""
Transfer SQLAlchemy 모델.

ledger 스키마에 속하는 계좌 간 이체 내역 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from datetime import date as date_type
from uuid import UUID

from sqlalchemy import DATE, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class Transfer(Base):
    """이체 모델 (ledger.transfers 테이블)."""

    __tablename__ = "transfers"
    __table_args__ = (
        Index("idx_transfer_user_date", "user_id", "transfer_date"),
        {"schema": "ledger", "comment": "계좌 간 이체 내역 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: auth.users.id (FK 제약 없음)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id",
    )
    # 논리적 FK: auth.family_groups.id (FK 제약 없음)
    family_group_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="논리적 FK → auth.family_groups.id",
    )
    # 논리적 FK: ledger.assets.id (FK 제약 없음) — 출금 자산
    from_asset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → ledger.assets.id (출금 자산)",
    )
    # 논리적 FK: ledger.assets.id (FK 제약 없음) — 입금 자산
    to_asset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → ledger.assets.id (입금 자산)",
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="이체 금액",
    )
    fee: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="이체 수수료 (기본값 0)",
    )
    description: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="이체 설명",
    )
    transfer_date: Mapped[date_type] = mapped_column(
        DATE, nullable=False, comment="이체 일자",
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
