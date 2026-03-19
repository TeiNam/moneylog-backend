"""
S3 Pre-signed URL 생성 서비스.

프로필 이미지 업로드를 위한 Pre-signed URL 생성 및 검증 로직을 담당한다.
"""

import logging
import uuid
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError
from app.schemas.upload import PresignedUrlResponse

logger = logging.getLogger(__name__)

# 허용된 이미지 확장자
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class S3Service:
    """S3 Pre-signed URL 생성 서비스."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._s3_client = boto3.client(
            "s3",
            region_name=settings.S3_REGION,
        )

    def generate_presigned_upload_url(
        self,
        user_id: UUID,
        file_extension: str,
    ) -> PresignedUrlResponse:
        """
        프로필 이미지 업로드용 Pre-signed URL을 생성한다.

        S3 키 형식: profile-images/{user_id}/{uuid}.{extension}
        만료: settings.S3_PRESIGNED_URL_EXPIRES (기본 300초)
        최대 파일 크기: settings.S3_PROFILE_IMAGE_MAX_SIZE (기본 5MB)

        Args:
            user_id: 사용자 UUID
            file_extension: 파일 확장자 (jpg, jpeg, png, webp)

        Returns:
            PresignedUrlResponse(upload_url, s3_key, expires_in)

        Raises:
            ExternalServiceError: S3 통신 오류 시
        """
        # S3 키 생성
        file_uuid = uuid.uuid4()
        s3_key = f"profile-images/{user_id}/{file_uuid}.{file_extension}"

        try:
            # Pre-signed POST URL 생성 (파일 크기 제한 포함)
            presigned_url = self._s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._settings.S3_BUCKET_NAME,
                    "Key": s3_key,
                    "ContentType": f"image/{file_extension}",
                },
                ExpiresIn=self._settings.S3_PRESIGNED_URL_EXPIRES,
            )
        except ClientError as e:
            logger.error("S3 Pre-signed URL 생성 실패: %s", str(e))
            raise ExternalServiceError(
                detail="파일 업로드 URL 생성에 실패했습니다"
            ) from e

        return PresignedUrlResponse(
            upload_url=presigned_url,
            s3_key=s3_key,
            expires_in=self._settings.S3_PRESIGNED_URL_EXPIRES,
        )

    def validate_file_extension(self, extension: str) -> bool:
        """허용된 확장자(jpg, jpeg, png, webp)인지 검증한다."""
        return extension.lower() in ALLOWED_EXTENSIONS

    def validate_s3_domain(self, url: str) -> bool:
        """프로필 이미지 URL이 유효한 S3 버킷 도메인인지 검증한다."""
        if not self._settings.S3_BUCKET_NAME:
            return False
        expected_domain = f"{self._settings.S3_BUCKET_NAME}.s3"
        return expected_domain in url
