"""
BedrockClient 단위 테스트.

boto3 클라이언트를 모킹하여 외부 API 의존성 없이 테스트한다.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.bedrock_client import BedrockClient, BedrockError


@pytest.fixture
def mock_boto3_client():
    """boto3 bedrock-runtime 클라이언트를 모킹한다."""
    with patch("app.services.bedrock_client.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        with patch("app.services.bedrock_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                BEDROCK_MODEL_ID="test-model",
                BEDROCK_REGION="us-east-1",
                BEDROCK_TIMEOUT=30,
            )
            client = BedrockClient()
            yield client, mock_client


@pytest.mark.asyncio
async def test_converse_success(mock_boto3_client):
    """converse 정상 호출을 검증한다."""
    client, mock_raw = mock_boto3_client
    mock_raw.converse.return_value = {
        "output": {"message": {"content": [{"text": "AI 응답입니다"}]}}
    }

    result = await client.converse(
        system_prompt="시스템 프롬프트",
        messages=[{"role": "user", "content": [{"text": "안녕하세요"}]}],
    )

    assert result == "AI 응답입니다"
    mock_raw.converse.assert_called_once()


@pytest.mark.asyncio
async def test_converse_with_image_success(mock_boto3_client):
    """converse_with_image 정상 호출을 검증한다."""
    client, mock_raw = mock_boto3_client
    mock_raw.converse.return_value = {
        "output": {"message": {"content": [{"text": "영수증 분석 결과"}]}}
    }

    result = await client.converse_with_image(
        system_prompt="시스템 프롬프트",
        image_bytes=b"fake-image-data",
        content_type="image/jpeg",
    )

    assert result == "영수증 분석 결과"
    mock_raw.converse.assert_called_once()


@pytest.mark.asyncio
async def test_converse_failure_raises_bedrock_error(mock_boto3_client):
    """converse API 호출 실패 시 BedrockError가 발생하는지 검증한다."""
    client, mock_raw = mock_boto3_client
    mock_raw.converse.side_effect = Exception("API 오류")

    with pytest.raises(BedrockError) as exc_info:
        await client.converse(
            system_prompt="시스템 프롬프트",
            messages=[{"role": "user", "content": [{"text": "테스트"}]}],
        )

    assert "AI 서비스 호출에 실패했습니다" in exc_info.value.detail


@pytest.mark.asyncio
async def test_converse_with_image_failure_raises_bedrock_error(mock_boto3_client):
    """converse_with_image API 호출 실패 시 BedrockError가 발생하는지 검증한다."""
    client, mock_raw = mock_boto3_client
    mock_raw.converse.side_effect = Exception("Vision API 오류")

    with pytest.raises(BedrockError) as exc_info:
        await client.converse_with_image(
            system_prompt="시스템 프롬프트",
            image_bytes=b"fake-image-data",
            content_type="image/png",
        )

    assert "AI 서비스 호출에 실패했습니다" in exc_info.value.detail


@pytest.mark.asyncio
async def test_converse_with_image_jpg_content_type(mock_boto3_client):
    """content_type이 image/jpg일 때 jpeg로 변환되는지 검증한다."""
    client, mock_raw = mock_boto3_client
    mock_raw.converse.return_value = {
        "output": {"message": {"content": [{"text": "결과"}]}}
    }

    await client.converse_with_image(
        system_prompt="프롬프트",
        image_bytes=b"data",
        content_type="image/jpg",
    )

    # 호출된 messages에서 format이 jpeg인지 확인
    call_args = mock_raw.converse.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
    image_block = messages[0]["content"][0]["image"]
    assert image_block["format"] == "jpeg"
