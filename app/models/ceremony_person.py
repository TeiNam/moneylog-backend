"""
CeremonyPerson SQLAlchemy 모델.

ledger 스키마에 속하는 경조사 인물 테이블을 정의한다.
특정 인물과의 경조사 누적 기록(보낸 금액, 받은 금액, 이벤트 횟수)을 관리한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from uuid import UUID

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class CeremonyPerson(Base):
    """경조사 인물 모델 (ledger.ceremony_persons 테이블)."""

    __tablename__ = "ceremony_persons"
    __table_args__ = (
        {"schema": "ledger", "comment": "경조사 인물 누적 기록 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: auth.users.id (FK 제약 없음)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id",
    )
    name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="인물 이름"
    )
    relationship: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="관계 (친구, 직장동료 등)"
    )
    total_sent: Mapped[int] = mapped_column(
        Integer, default=0, comment="보낸 총 금액 (기본값 0)"
    )
    total_received: Mapped[int] = mapped_column(
        Integer, default=0, comment="받은 총 금액 (기본값 0)"
    )
    event_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="경조사 이벤트 횟수 (기본값 0)"
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
