"""
프로필 이미지 업로드 관련 Pydantic 스키마.

S3 Pre-signed URL 발급 요청 및 응답 모델을 정의한다.
"""

from pydantic import BaseModel, Field


class ProfileImageUploadRequest(BaseModel):
    """프로필 이미지 업로드 URL 요청 스키마."""

    file_extension: str = Field(
        ...,
        pattern=r"^(jpg|jpeg|png|webp)$",
        description="파일 확장자 (jpg, jpeg, png, webp)",
    )


class PresignedUrlResponse(BaseModel):
    """Pre-signed URL 응답 스키마."""

    upload_url: str = Field(..., description="S3 업로드용 Pre-signed URL")
    s3_key: str = Field(..., description="S3 객체 키")
    expires_in: int = Field(default=300, description="URL 만료 시간 (초)")
