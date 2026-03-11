"""
CategoryConfig SQLAlchemy 모델.

ledger 스키마에 속하는 카테고리 설정 테이블을 정의한다.
영역별 대분류/소분류 카테고리를 사용자 또는 가족 그룹 단위로 관리한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from uuid import UUID

from sqlalchemy import ARRAY, Boolean, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class CategoryConfig(Base):
    """카테고리 설정 모델 (ledger.category_configs 테이블)."""

    __tablename__ = "category_configs"
    __table_args__ = (
        Index(
            "idx_category_configs_owner_id_owner_type_area_type",
            "owner_id",
            "owner_type",
            "area",
            "type",
        ),
        {"schema": "ledger", "comment": "카테고리 설정 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: owner_type에 따라 auth.users.id 또는 auth.family_groups.id 참조 (FK 제약 없음)
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id (owner_type=FAMILY_GROUP일 때 auth.family_groups.id)",
    )
    owner_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="소유자 유형: USER, FAMILY_GROUP",
    )
    area: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="거래 영역: GENERAL, CAR, SUBSCRIPTION, EVENT",
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="거래 유형: INCOME, EXPENSE",
    )
    major_category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="대분류 카테고리"
    )
    # PostgreSQL ARRAY(Text) 타입: 소분류 카테고리 목록
    minor_categories: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
        comment="소분류 카테고리 목록",
    )
    icon: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="카테고리 아이콘"
    )
    color: Mapped[str | None] = mapped_column(
        String(7), nullable=True, comment="카테고리 색상 (#RRGGBB)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="활성화 여부 (기본값 true)"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="기본 카테고리 여부 (기본값 false)"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="정렬 순서"
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
