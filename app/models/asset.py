"""
Asset SQLAlchemy 모델.

ledger 스키마에 속하는 자산(결제수단) 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class Asset(Base):
    """자산(결제수단) 모델 (ledger.assets 테이블)."""

    __tablename__ = "assets"
    __table_args__ = (
        Index("idx_assets_user_id", "user_id"),
        Index("idx_assets_family_group_id", "family_group_id"),
        {"schema": "ledger", "comment": "자산(결제수단) 테이블"},
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
    ownership: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="소유권: PERSONAL, SHARED",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="자산 이름"
    )
    asset_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="자산 유형: BANK_ACCOUNT, CREDIT_CARD, DEBIT_CARD, CASH, INVESTMENT, OTHER",
    )
    institution: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="금융기관명"
    )
    balance: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="잔액"
    )
    memo: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="메모"
    )
    icon: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="아이콘"
    )
    color: Mapped[str | None] = mapped_column(
        String(7), nullable=True, comment="색상 코드 (#RRGGBB)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="활성 여부"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="정렬 순서"
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
