"""
에러 응답 관련 Pydantic 스키마.

통일된 에러 응답 구조와 필드별 유효성 검증 오류 상세 모델을 정의한다.
"""

from pydantic import BaseModel, Field


class FieldErrorDetail(BaseModel):
    """필드별 유효성 검증 오류 상세 스키마."""

    field: str = Field(..., description="오류가 발생한 필드명")
    message: str = Field(..., description="오류 메시지")


class ErrorResponseSchema(BaseModel):
    """통일된 에러 응답 스키마."""

    error_code: str = Field(..., description="에러 코드 (UPPER_SNAKE_CASE)")
    message: str = Field(..., description="에러 메시지")
    details: list[FieldErrorDetail] | None = Field(
        default=None, description="필드별 유효성 검증 오류 상세 (선택적)"
    )
