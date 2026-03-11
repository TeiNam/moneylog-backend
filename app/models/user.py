"""
User 및 EmailVerification SQLAlchemy 모델.

auth 스키마에 속하는 사용자 및 이메일 인증 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import TIMESTAMP, Boolean, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class User(Base):
    """사용자 모델 (auth.users 테이블)."""

    __tablename__ = "users"
    __table_args__ = (
        {"schema": "auth", "comment": "사용자 계정 정보 테이블"},
    )

    id: Mapped[uuid_pk]
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="SSO 사용자는 null"
    )
    profile_image: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    auth_provider: Mapped[str] = mapped_column(
        String(20),
        default="EMAIL",
        comment="인증 제공자: EMAIL, GOOGLE, APPLE, KAKAO",
    )
    # 논리적 FK: auth.family_groups.id (FK 제약 없음)
    family_group_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="논리적 FK → auth.family_groups.id",
    )
    role_in_group: Mapped[str] = mapped_column(
        String(20),
        default="MEMBER",
        comment="그룹 내 역할: OWNER, MEMBER",
    )
    # 논리적 FK: ledger.assets.id (FK 제약 없음)
    default_asset_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="논리적 FK → ledger.assets.id",
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="이메일 인증 완료 여부"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        comment="계정 상태: ACTIVE, DORMANT, WITHDRAWN",
    )
    created_at: Mapped[created_at]
    last_login_at: Mapped[nullable_timestamp]


class EmailVerification(Base):
    """이메일 인증 코드 모델 (auth.email_verifications 테이블)."""

    __tablename__ = "email_verifications"
    __table_args__ = (
        {"schema": "auth", "comment": "이메일 인증 코드 관리 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: auth.users.id (FK 제약 없음)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id",
    )
    code: Mapped[str] = mapped_column(
        String(6), nullable=False, comment="6자리 숫자 인증 코드"
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, comment="인증 코드 만료 시각"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, comment="인증 시도 횟수"
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="인증 코드 유효 여부"
    )
    created_at: Mapped[created_at]
