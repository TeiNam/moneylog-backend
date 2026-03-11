"""
Subscription SQLAlchemy 모델.

ledger 스키마에 속하는 구독 관리 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from datetime import date as date_type
from uuid import UUID

from sqlalchemy import DATE, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class Subscription(Base):
    """구독 모델 (ledger.subscriptions 테이블)."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("idx_subscriptions_user_id", "user_id"),
        Index("idx_subscriptions_user_id_status", "user_id", "status"),
        {"schema": "ledger", "comment": "구독 관리 테이블"},
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
    service_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="구독 서비스 이름",
    )
    category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="구독 카테고리: OTT, MUSIC, CLOUD, PRODUCTIVITY, AI, GAME, NEWS, OTHER",
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="결제 금액",
    )
    cycle: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="결제 주기: MONTHLY, YEARLY, WEEKLY",
    )
    billing_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="결제일 (1~31, WEEKLY의 경우 start_date 요일 기준)",
    )
    # 논리적 FK: ledger.assets.id (FK 제약 없음)
    asset_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="논리적 FK → ledger.assets.id",
    )
    start_date: Mapped[date_type] = mapped_column(
        DATE, nullable=False, comment="구독 시작일",
    )
    end_date: Mapped[date_type | None] = mapped_column(
        DATE, nullable=True, comment="구독 종료일",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="구독 상태: ACTIVE, PAUSED, CANCELLED",
    )
    notify_before_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="결제 전 알림 일수 (기본값 1)",
    )
    memo: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="메모",
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
