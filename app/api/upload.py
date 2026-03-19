"""
파일 업로드 관련 HTTP 엔드포인트.

프로필 이미지 업로드를 위한 S3 Pre-signed URL 발급을 제공한다.
"""

import logging

from fastapi import APIRouter, Depends, status

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestError
from app.models.user import User
from app.schemas.upload import PresignedUrlResponse, ProfileImageUploadRequest
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post(
    "/profile-image-url",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="프로필 이미지 업로드 Pre-signed URL 발급",
)
def create_profile_image_upload_url(
    body: ProfileImageUploadRequest,
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PresignedUrlResponse:
    """인증된 사용자에게 프로필 이미지 업로드용 S3 Pre-signed URL을 발급한다."""
    s3_service = S3Service(settings)

    # 확장자 검증
    if not s3_service.validate_file_extension(body.file_extension):
        raise BadRequestError(
            detail="허용되지 않은 파일 확장자입니다. 허용: jpg, jpeg, png, webp"
        )

    # Pre-signed URL 생성
    return s3_service.generate_presigned_upload_url(
        user_id=current_user.id,
        file_extension=body.file_extension,
    )
