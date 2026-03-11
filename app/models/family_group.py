"""
FamilyGroup SQLAlchemy 모델.

auth 스키마에 속하는 가족 그룹 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, uuid_pk


class FamilyGroup(Base):
    """가족 그룹 모델 (auth.family_groups 테이블)."""

    __tablename__ = "family_groups"
    __table_args__ = (
        {"schema": "auth", "comment": "가족 그룹 테이블"},
    )

    id: Mapped[uuid_pk]
    name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="그룹 이름"
    )
    # 8자리 영숫자 초대 코드 (유니크 인덱스)
    invite_code: Mapped[str] = mapped_column(
        String(8),
        unique=True,
        index=True,
        nullable=False,
        comment="8자리 영숫자 초대 코드",
    )
    invite_code_expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment="초대 코드 만료 시각",
    )
    # 논리적 FK: auth.users.id (FK 제약 없음)
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id (그룹장)",
    )
    created_at: Mapped[created_at]
