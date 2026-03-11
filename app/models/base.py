"""
SQLAlchemy DeclarativeBase 및 공통 타입 어노테이션 정의.

모든 모델은 이 Base 클래스를 상속하며,
공통 컬럼 타입을 Annotated 타입으로 재사용한다.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from sqlalchemy import TIMESTAMP, BigInteger, Identity, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


# 공통 타입 어노테이션 정의
# UUID 기본키: 자동 생성되는 UUID v4
uuid_pk = Annotated[
    UUID,
    mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
]

# BigInt 기본키: IDENTITY(always=True) 기반 자동 증가 정수 PK
# 고빈도 테이블(transactions, ai_chat_messages)에서 인덱스 성능 향상을 위해 사용
bigint_pk = Annotated[
    int,
    mapped_column(BigInteger, Identity(always=True), primary_key=True),
]

# 생성 시각: 서버 기본값으로 현재 시각 (timezone 포함)
created_at = Annotated[
    datetime,
    mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    ),
]

# 수정 시각 (nullable): 선택적 타임스탬프
nullable_timestamp = Annotated[
    datetime | None,
    mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    ),
]


class Base(DeclarativeBase):
    """모든 SQLAlchemy 모델의 기본 클래스."""

    pass
