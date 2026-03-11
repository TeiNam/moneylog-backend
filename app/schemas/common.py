"""
공통 응답 스키마 모듈.

헬스체크, 에러 응답 등 여러 엔드포인트에서 공유하는 Pydantic 모델을 정의한다.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """헬스체크 응답 스키마."""

    status: str
    database: str
    version: str


class ErrorResponse(BaseModel):
    """에러 응답 스키마."""

    detail: str
