"""
ChatMessage SQLAlchemy 모델.

ledger 스키마에 속하는 AI 채팅 메시지 테이블을 정의한다.
FK 제약조건 없이 논리적 FK만 사용한다 (PostgreSQL 가이드라인 준수).
월별 RANGE 파티셔닝이 적용되어 created_at 기준으로 파티션된다.
"""

from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Identity, Index, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at


class ChatMessage(Base):
    """AI 채팅 메시지 모델 (ledger.ai_chat_messages 테이블)."""

    __tablename__ = "ai_chat_messages"
    __table_args__ = (
        # 복합 PK: 파티션 키(created_at)는 반드시 PK에 포함되어야 함
        PrimaryKeyConstraint("id", "created_at"),
        Index("idx_ai_chat_messages_session_id_created_at", "session_id", "created_at"),
        UniqueConstraint("public_id", name="uidx_ai_chat_messages_public_id"),
        {
            "schema": "ledger",
            "comment": "AI 채팅 메시지 테이블",
            "postgresql_partition_by": "RANGE (created_at)",
        },
    )

    # BigInteger + Identity PK (복합 PK의 일부, created_at과 함께 구성)
    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True),
    )
    # 외부 노출용 UUID 식별자 (API에서 사용)
    public_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        default=uuid4,
        nullable=False,
        comment="외부 노출용 UUID (API 식별자)",
    )
    # 논리적 FK: ledger.ai_chat_sessions.id (FK 제약 없음)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="논리적 FK → ledger.ai_chat_sessions.id",
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="메시지 역할: USER, ASSISTANT",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="메시지 내용",
    )
    extracted_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="AI가 추출한 거래 데이터 (JSON)",
    )
    created_at: Mapped[created_at]
