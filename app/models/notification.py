"""
Notification SQLAlchemy 모델.

ledger 스키마에 속하는 알림 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from uuid import UUID

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, uuid_pk


class Notification(Base):
    """알림 모델 (ledger.notifications 테이블)."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_notifications_user_id_is_read", "user_id", "is_read"),
        {"schema": "ledger", "comment": "알림 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: auth.users.id (FK 제약 없음)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id",
    )
    # 논리적 FK: ledger.subscriptions.id (FK 제약 없음)
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → ledger.subscriptions.id",
    )
    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="알림 유형: SUBSCRIPTION_PAYMENT",
    )
    title: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="알림 제목",
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False, comment="알림 내용",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="읽음 여부",
    )
    created_at: Mapped[created_at]
