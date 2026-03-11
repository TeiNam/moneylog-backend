"""
AIFeedback SQLAlchemy 모델.

ledger 스키마에 속하는 AI 오분류 피드백 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
"""

from uuid import UUID

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, uuid_pk


class AIFeedback(Base):
    """AI 피드백 모델 (ledger.ai_feedbacks 테이블)."""

    __tablename__ = "ai_feedbacks"
    __table_args__ = (
        Index("idx_ai_feedbacks_user_id_created_at", "user_id", "created_at"),
        Index("idx_ai_feedbacks_transaction_id", "transaction_id"),
        {"schema": "ledger", "comment": "AI 오분류 피드백 테이블"},
    )

    id: Mapped[uuid_pk]
    # 논리적 FK: auth.users.id (FK 제약 없음)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → auth.users.id",
    )
    # 논리적 FK: ledger.transactions.id (FK 제약 없음, bigint)
    transaction_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="논리적 FK → ledger.transactions.id",
    )
    feedback_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="피드백 유형: CATEGORY_CORRECTION, AMOUNT_CORRECTION, DESCRIPTION_CORRECTION",
    )
    original_value: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="원래 값",
    )
    corrected_value: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="수정된 값",
    )
    created_at: Mapped[created_at]
