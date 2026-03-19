"""
Upload Router 단위 테스트.

Pre-signed URL 발급, 허용되지 않은 확장자 거부, S3 오류 시 502 응답,
인증되지 않은 사용자 요청 거부를 검증한다.

Requirements: 1.1, 1.4, 1.6
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import ExternalServiceError
from app.main import app
from app.models.user import User
from app.schemas.upload import PresignedUrlResponse


# ---------------------------------------------------------------------------
# 테스트용 헬퍼
# ---------------------------------------------------------------------------

def _make_fake_user() -> User:
    """테스트용 가짜 User 객체를 생성한다."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "test@example.com"
    user.nickname = "테스트유저"
    return user


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_user():
    """테스트용 가짜 사용자 픽스처."""
    return _make_fake_user()


@pytest.fixture
async def authenticated_client(fake_user):
    """인증된 사용자로 오버라이드된 AsyncClient를 제공한다."""
    # get_current_user 의존성을 가짜 사용자로 오버라이드
    app.dependency_overrides[get_current_user] = lambda: fake_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def unauthenticated_client():
    """인증 없는 AsyncClient를 제공한다 (의존성 오버라이드 없음)."""
    # 기존 오버라이드 정리
    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 1. 인증된 사용자가 유효한 확장자로 요청 시 Pre-signed URL 정상 반환
#    Requirements: 1.1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["jpg", "jpeg", "png", "webp"])
async def test_presigned_url_success(authenticated_client, fake_user, extension):
    """인증된 사용자가 허용된 확장자로 요청하면 Pre-signed URL이 정상 반환되는지 검증한다."""
    mock_response = PresignedUrlResponse(
        upload_url=f"https://test-bucket.s3.amazonaws.com/profile-images/{fake_user.id}/test.{extension}",
        s3_key=f"profile-images/{fake_user.id}/test-uuid.{extension}",
        expires_in=300,
    )

    with patch(
        "app.api.upload.S3Service"
    ) as MockS3Service:
        # S3Service 인스턴스 모킹
        mock_instance = MockS3Service.return_value
        mock_instance.validate_file_extension.return_value = True
        mock_instance.generate_presigned_upload_url.return_value = mock_response

        response = await authenticated_client.post(
            "/api/v1/upload/profile-image-url",
            json={"file_extension": extension},
        )

    assert response.status_code == 200

    body = response.json()
    assert "upload_url" in body
    assert "s3_key" in body
    assert "expires_in" in body
    assert body["expires_in"] == 300


# ---------------------------------------------------------------------------
# 2. 허용되지 않은 확장자로 요청 시 HTTP 400 응답
#    Requirements: 1.4
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["gif", "bmp", "tiff", "svg"])
async def test_invalid_extension_returns_400(authenticated_client, extension):
    """허용되지 않은 확장자로 요청하면 HTTP 422(Pydantic 검증) 또는 400 응답을 반환하는지 검증한다."""
    # Pydantic 스키마의 pattern 검증에 의해 422가 반환됨
    response = await authenticated_client.post(
        "/api/v1/upload/profile-image-url",
        json={"file_extension": extension},
    )

    # Pydantic pattern 검증 실패 시 422, 서비스 레벨 검증 시 400
    assert response.status_code in (400, 422)

    body = response.json()
    assert "error_code" in body
    assert "message" in body


# ---------------------------------------------------------------------------
# 3. S3 서비스 오류 발생 시 HTTP 502 응답
#    Requirements: 1.6
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s3_error_returns_502(authenticated_client):
    """S3 서비스 오류 발생 시 HTTP 502 응답을 반환하는지 검증한다."""
    with patch(
        "app.api.upload.S3Service"
    ) as MockS3Service:
        mock_instance = MockS3Service.return_value
        mock_instance.validate_file_extension.return_value = True
        mock_instance.generate_presigned_upload_url.side_effect = ExternalServiceError(
            detail="파일 업로드 URL 생성에 실패했습니다"
        )

        response = await authenticated_client.post(
            "/api/v1/upload/profile-image-url",
            json={"file_extension": "jpg"},
        )

    assert response.status_code == 502

    body = response.json()
    assert body["error_code"] == "EXTERNAL_SERVICE_ERROR"
    assert "파일 업로드 URL 생성에 실패했습니다" in body["message"]


# ---------------------------------------------------------------------------
# 4. 인증되지 않은 사용자의 요청 거부
#    Requirements: 1.1 (인증 필수)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(unauthenticated_client):
    """인증되지 않은 사용자의 요청이 거부되는지 검증한다 (401 응답)."""
    response = await unauthenticated_client.post(
        "/api/v1/upload/profile-image-url",
        json={"file_extension": "jpg"},
    )

    # Bearer 토큰 없이 요청 시 401 Unauthorized
    assert response.status_code == 401
