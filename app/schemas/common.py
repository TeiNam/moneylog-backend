"""
공통 응답 스키마 모듈.

헬스체크, 에러 응답 등 여러 엔드포인트에서 공유하는 Pydantic 모델을 정의한다.
"""

from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.utils.timezone_utils import ensure_utc_iso


class UTCDatetimeResponse(BaseModel):
    """datetime 필드를 ISO 8601 UTC(Z 접미사) 형식으로 직렬화하는 베이스 응답 모델.

    모든 응답 스키마에서 datetime 필드가 있으면 이 클래스를 상속하여
    일관된 UTC ISO 8601 형식(Z 접미사)으로 반환한다.
    """

    @field_serializer("*", mode="plain")
    @classmethod
    def serialize_datetime_fields(cls, value: object) -> object:
        """datetime 필드를 ensure_utc_iso로 직렬화한다."""
        if isinstance(value, datetime):
            return ensure_utc_iso(value)
        return value


class HealthResponse(BaseModel):
    """헬스체크 응답 스키마."""

    status: str
    database: str
    version: str


class ErrorResponse(BaseModel):
    """에러 응답 스키마."""

    detail: str
