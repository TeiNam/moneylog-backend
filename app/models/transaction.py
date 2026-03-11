"""
Transaction, CarExpenseDetail, CeremonyEvent SQLAlchemy 모델.

ledger 스키마에 속하는 거래 및 관련 상세 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from datetime import date as date_type
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DATE, DECIMAL, BigInteger, Boolean, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, bigint_pk, created_at, nullable_timestamp, uuid_pk


class Transaction(Base):
    """거래 모델 (ledger.transactions 테이블)."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_transactions_user_id_date", "user_id", "date"),
        Index("idx_transactions_family_group_id_date", "family_group_id", "date"),
        Index("idx_transactions_asset_id_date", "asset_id", "date"),
        Index("idx_transactions_area_date", "area", "date"),
        Index("idx_transactions_user_id_is_private", "user_id", "is_private"),
        # 공개 거래(is_private=false) 조회 최적화를 위한 부분 인덱스
        Index(
            "idx_transactions_user_id_date_not_private",
            "user_id",
            "date",
            postgresql_where=text("is_private = false"),
        ),
        UniqueConstraint("public_id", name="uidx_transactions_public_id"),
        {"schema": "ledger", "comment": "수입/지출 거래 내역 테이블"},
    )

    id: Mapped[bigint_pk]
    # 외부 노출용 UUID 식별자 (API에서 사용)
    public_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        default=uuid4,
        nullable=False,
        comment="외부 노출용 UUID (API 식별자)",
    )
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
    date: Mapped[date_type] = mapped_column(
        DATE, nullable=False, comment="거래 일자"
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
    minor_category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="소분류 카테고리"
    )
    description: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="거래 설명"
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="결제 금액"
    )
    discount: Mapped[int] = mapped_column(
        Integer, default=0, comment="할인 금액 (기본값 0)"
    )
    actual_amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="실지출 금액 (amount - discount)"
    )
    # 논리적 FK: ledger.assets.id (FK 제약 없음)
    asset_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="논리적 FK → ledger.assets.id",
    )
    memo: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="메모"
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="입력 출처: MANUAL, AI_CHAT, RECEIPT_SCAN, SUBSCRIPTION_AUTO",
    )
    is_private: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="비밀 거래 여부 (기본값 false)",
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]


class CarExpenseDetail(Base):
    """차계부 상세 모델 (ledger.car_expense_details 테이블)."""

    __tablename__ = "car_expense_details"
    __table_args__ = (
        {"schema": "ledger", "comment": "차계부 비용 상세 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: ledger.transactions.id (FK 제약 없음, bigint)
    transaction_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="논리적 FK → ledger.transactions.id",
    )
    car_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="차계부 비용 유형: FUEL, MAINTENANCE, INSURANCE 등",
    )
    fuel_amount_liter: Mapped[Decimal | None] = mapped_column(
        DECIMAL, nullable=True, comment="주유량 (리터)"
    )
    fuel_unit_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="연료 단가 (원/리터)"
    )
    odometer: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="주행 거리 (km)"
    )
    station_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="주유소/정비소 이름"
    )


class CeremonyEvent(Base):
    """경조사 이벤트 모델 (ledger.ceremony_events 테이블)."""

    __tablename__ = "ceremony_events"
    __table_args__ = (
        {"schema": "ledger", "comment": "경조사 이벤트 상세 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: ledger.transactions.id (FK 제약 없음, bigint)
    transaction_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="논리적 FK → ledger.transactions.id",
    )
    direction: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="경조사 방향: SENT, RECEIVED",
    )
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="이벤트 유형: WEDDING, FUNERAL, FIRST_BIRTHDAY 등",
    )
    person_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="대상 인물 이름"
    )
    relationship: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="관계 (친구, 직장동료 등)"
    )
    venue: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="행사 장소"
    )
