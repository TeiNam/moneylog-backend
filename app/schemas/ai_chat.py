"""AI 채팅 관련 Pydantic 스키마."""

# Python 3.14 + Pydantic 호환성을 위한 어노테이션 지연 평가
from __future__ import annotations

import datetime as _dt
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreateRequest(BaseModel):
    """채팅 세션 생성 요청."""
    title: str | None = Field(None, max_length=200)


class ChatSessionResponse(BaseModel):
    """채팅 세션 응답."""
    id: UUID
    user_id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class ChatMessageRequest(BaseModel):
    """채팅 메시지 전송 요청."""
    content: str = Field(..., min_length=1, max_length=2000)


class ExtractedTransactionData(BaseModel):
    """AI가 추출한 거래 데이터."""
    # 필드명 'date'가 datetime.date 타입과 이름 충돌하므로 _dt.date로 참조
    date: _dt.date | None = None
    area: str | None = None
    type: str | None = None
    major_category: str | None = None
    minor_category: str | None = None
    description: str | None = None
    amount: int | None = None
    discount: int | None = Field(default=0)
    actual_amount: int | None = None
    asset_id: UUID | None = None


class ChatMessageResponse(BaseModel):
    """채팅 메시지 응답."""
    id: UUID
    session_id: UUID
    role: str
    content: str
    extracted_data: dict | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChatSessionDetailResponse(BaseModel):
    """채팅 세션 상세 응답 (메시지 목록 포함)."""
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]


class TransactionConfirmRequest(BaseModel):
    """거래 확정 요청 (수정 데이터 선택)."""
    overrides: ExtractedTransactionData | None = None
