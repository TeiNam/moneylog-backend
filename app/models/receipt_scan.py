"""
ReceiptScan SQLAlchemy 모델.

ledger 스키마에 속하는 영수증 OCR 스캔 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from uuid import UUID

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, nullable_timestamp, uuid_pk


class ReceiptScan(Base):
    """영수증 스캔 모델 (ledger.receipt_scans 테이블)."""

    __tablename__ = "receipt_scans"
    __table_args__ = (
        Index("idx_receipt_scans_user_id_created_at", "user_id", "created_at"),
        {"schema": "ledger", "comment": "영수증 OCR 스캔 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: auth.users.id (FK 제약 없음)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id",
    )
    image_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="영수증 이미지 URL",
    )
    raw_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="OCR 추출 원본 텍스트",
    )
    extracted_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="추출된 거래 데이터 (JSON)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="스캔 상태: PENDING, COMPLETED, FAILED",
    )
    # 논리적 FK: ledger.transactions.id (FK 제약 없음, bigint)
    transaction_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="논리적 FK → ledger.transactions.id",
    )
    created_at: Mapped[created_at]
    updated_at: Mapped[nullable_timestamp]
