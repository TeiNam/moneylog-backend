"""
S3 서비스 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 S3 Pre-signed URL 서비스의 핵심 속성을 검증한다.
"""

import re
import uuid
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from app.core.config import Settings
from app.services.s3_service import ALLOWED_EXTENSIONS, S3Service


# ---------------------------------------------------------------------------
# 테스트용 전략(Strategy) 정의
# ---------------------------------------------------------------------------

# UUID 전략
uuid_strategy = st.uuids()

# 허용된 확장자 전략
allowed_extension_strategy = st.sampled_from(sorted(ALLOWED_EXTENSIONS))

# 허용되지 않은 확장자 전략 — {"jpg", "jpeg", "png", "webp"} 이외의 문자열
disallowed_extension_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=10,
).filter(lambda s: s.lower() not in ALLOWED_EXTENSIONS)

# S3 버킷 이름 전략
bucket_name_strategy = st.from_regex(r"[a-z][a-z0-9\-]{2,20}", fullmatch=True)

# URL 전략 (임의의 문자열)
url_strategy = st.text(min_size=1, max_size=300)


# ---------------------------------------------------------------------------
# 테스트용 Settings 헬퍼
# ---------------------------------------------------------------------------

def _create_test_settings(bucket_name: str = "test-bucket") -> Settings:
    """테스트용 Settings 인스턴스를 생성한다."""
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test-secret-key",
        S3_BUCKET_NAME=bucket_name,
        S3_REGION="ap-northeast-2",
        S3_PRESIGNED_URL_EXPIRES=300,
        S3_PROFILE_IMAGE_MAX_SIZE=5 * 1024 * 1024,
    )


# ---------------------------------------------------------------------------
# Property 1: S3 키 형식 불변식
# Feature: frontend-integration-improvements, Property 1: S3 키 형식 불변식
# **Validates: Requirements 1.1, 1.2**
# ---------------------------------------------------------------------------

# S3 키 형식 정규식: profile-images/{user_id}/{uuid}.{extension}
_S3_KEY_PATTERN = re.compile(
    r"^profile-images/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"\.(\w+)$"
)


@hypothesis_settings(max_examples=30, deadline=None)
@given(user_id=uuid_strategy, extension=allowed_extension_strategy)
def test_s3_key_format_invariant(user_id: uuid.UUID, extension: str):
    """임의의 user_id(UUID)와 허용된 파일 확장자에 대해,
    S3Service가 생성하는 S3 키는 profile-images/{user_id}/{uuid}.{extension} 형식을 따르며,
    키 내의 user_id는 입력과 일치하고, 확장자도 입력과 일치해야 한다.
    """
    settings = _create_test_settings()

    # boto3 S3 클라이언트를 모킹하여 실제 AWS 호출 방지
    with patch("app.services.s3_service.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.generate_presigned_url.return_value = (
            f"https://test-bucket.s3.amazonaws.com/presigned-url"
        )

        service = S3Service(settings)
        result = service.generate_presigned_upload_url(user_id, extension)

    s3_key = result.s3_key

    # 1) S3 키가 올바른 형식을 따르는지 검증
    match = _S3_KEY_PATTERN.match(s3_key)
    assert match is not None, f"S3 키 형식 불일치: {s3_key}"

    # 2) 키 내의 user_id가 입력 user_id와 일치하는지 검증
    key_user_id = match.group(1)
    assert key_user_id == str(user_id), (
        f"user_id 불일치: {key_user_id} != {user_id}"
    )

    # 3) 확장자가 입력 확장자와 일치하는지 검증
    key_extension = match.group(3)
    assert key_extension == extension, (
        f"확장자 불일치: {key_extension} != {extension}"
    )

    # 4) expires_in이 설정값과 일치하는지 검증
    assert result.expires_in == settings.S3_PRESIGNED_URL_EXPIRES


# ---------------------------------------------------------------------------
# Property 2: 허용되지 않은 확장자 거부
# Feature: frontend-integration-improvements, Property 2: 허용되지 않은 확장자 거부
# **Validates: Requirements 1.4**
# ---------------------------------------------------------------------------


@hypothesis_settings(max_examples=30, deadline=None)
@given(extension=disallowed_extension_strategy)
def test_disallowed_extension_rejected(extension: str):
    """임의의 문자열 중 {"jpg", "jpeg", "png", "webp"} 집합에 속하지 않는 문자열에 대해,
    validate_file_extension은 항상 False를 반환해야 한다.
    """
    settings = _create_test_settings()

    with patch("app.services.s3_service.boto3"):
        service = S3Service(settings)

    result = service.validate_file_extension(extension)
    assert result is False, (
        f"허용되지 않은 확장자 '{extension}'에 대해 True 반환"
    )


@hypothesis_settings(max_examples=30, deadline=None)
@given(extension=allowed_extension_strategy)
def test_allowed_extension_accepted(extension: str):
    """허용된 확장자에 대해 validate_file_extension은 True를 반환해야 한다."""
    settings = _create_test_settings()

    with patch("app.services.s3_service.boto3"):
        service = S3Service(settings)

    result = service.validate_file_extension(extension)
    assert result is True, (
        f"허용된 확장자 '{extension}'에 대해 False 반환"
    )


# ---------------------------------------------------------------------------
# Property 3: S3 URL 도메인 검증
# Feature: frontend-integration-improvements, Property 3: S3 URL 도메인 검증
# **Validates: Requirements 1.7**
# ---------------------------------------------------------------------------


@hypothesis_settings(max_examples=30, deadline=None)
@given(bucket_name=bucket_name_strategy)
def test_s3_domain_validation_accepts_valid_urls(bucket_name: str):
    """설정된 S3 버킷 도메인을 포함하는 URL에 대해
    validate_s3_domain은 True를 반환해야 한다.
    """
    settings = _create_test_settings(bucket_name=bucket_name)

    with patch("app.services.s3_service.boto3"):
        service = S3Service(settings)

    # 유효한 S3 URL 생성
    valid_url = f"https://{bucket_name}.s3.ap-northeast-2.amazonaws.com/profile-images/test.jpg"
    assert service.validate_s3_domain(valid_url) is True, (
        f"유효한 S3 URL에 대해 False 반환: {valid_url}"
    )


@hypothesis_settings(max_examples=30, deadline=None)
@given(
    bucket_name=bucket_name_strategy,
    url=url_strategy,
)
def test_s3_domain_validation_rejects_invalid_urls(bucket_name: str, url: str):
    """설정된 S3 버킷 도메인을 포함하지 않는 URL에 대해
    validate_s3_domain은 False를 반환해야 한다.
    """
    settings = _create_test_settings(bucket_name=bucket_name)

    with patch("app.services.s3_service.boto3"):
        service = S3Service(settings)

    # 버킷 도메인이 포함되지 않도록 필터링
    expected_domain = f"{bucket_name}.s3"
    if expected_domain in url:
        # 이 경우는 유효한 URL이므로 True가 맞음 — 스킵
        return

    assert service.validate_s3_domain(url) is False, (
        f"유효하지 않은 URL에 대해 True 반환: {url}"
    )
