"""영수증 관련 Pydantic 스키마."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.ai_chat import ExtractedTransactionData


class ReceiptScanResponse(BaseModel):
    """영수증 스캔 응답."""
    id: UUID
    user_id: UUID
    image_url: str | None
    raw_text: str | None
    extracted_data: dict | None
    status: str
    transaction_id: int | None
    created_at: datetime
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class ReceiptConfirmRequest(BaseModel):
    """영수증 거래 확정 요청 (수정 데이터 선택)."""
    overrides: ExtractedTransactionData | None = None
