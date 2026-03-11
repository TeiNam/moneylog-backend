"""
Goal SQLAlchemy 모델.

ledger 스키마에 속하는 재무 목표 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from datetime import date as date_type
from uuid import UUID

from sqlalchemy import DATE, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class Goal(Base):
    """목표 모델 (ledger.goals 테이블)."""

    __tablename__ = "goals"
    __table_args__ = (
        Index("idx_goals_user_id_status", "user_id", "status"),
        {"schema": "ledger", "comment": "재무 목표 테이블"},
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
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="목표 유형: MONTHLY_SAVING, SAVING_RATE, SPECIAL",
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="목표 제목",
    )
    target_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="목표 금액",
    )
    current_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="현재 달성 금액",
    )
    start_date: Mapped[date_type] = mapped_column(
        DATE, nullable=False, comment="목표 시작일",
    )
    end_date: Mapped[date_type] = mapped_column(
        DATE, nullable=False, comment="목표 종료일",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="목표 상태: ACTIVE, COMPLETED, FAILED",
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
