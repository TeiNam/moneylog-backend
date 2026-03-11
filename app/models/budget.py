"""
Budget SQLAlchemy 모델.

ledger 스키마에 속하는 월별 카테고리별 예산 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from uuid import UUID

from sqlalchemy import Index, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class Budget(Base):
    """예산 모델 (ledger.budgets 테이블)."""

    __tablename__ = "budgets"
    __table_args__ = (
        Index("idx_budgets_user_id_year_month", "user_id", "year", "month"),
        {"schema": "ledger", "comment": "월별 카테고리별 예산 테이블"},
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
    year: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="연도",
    )
    month: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="월 (1~12)",
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="대분류 카테고리명",
    )
    budget_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="예산 금액",
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
