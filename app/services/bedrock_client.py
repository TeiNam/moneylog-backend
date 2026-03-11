"""
Amazon Bedrock API 통신 클라이언트.

boto3 bedrock-runtime 동기 클라이언트를 asyncio.to_thread로 감싸서
비동기 호출을 지원한다. 테스트 시 이 클래스를 모킹하여 Bedrock 의존성을 제거한다.
"""

import asyncio
import logging

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BedrockError(Exception):
    """Bedrock API 호출 실패 시 발생하는 예외."""

    def __init__(self, detail: str = "AI 서비스 호출에 실패했습니다") -> None:
        self.detail = detail
        super().__init__(detail)


class BedrockClient:
    """Amazon Bedrock API 통신 클라이언트."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model_id = settings.BEDROCK_MODEL_ID
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.BEDROCK_REGION,
            config=BotoConfig(
                read_timeout=settings.BEDROCK_TIMEOUT,
                connect_timeout=10,
            ),
        )

    async def converse(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> str:
        """Bedrock Converse API 호출 (텍스트 전용)."""
        try:
            response = await asyncio.to_thread(
                self._client.converse,
                modelId=self._model_id,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={"maxTokens": max_tokens},
            )
            return response["output"]["message"]["content"][0]["text"]
        except Exception as e:
            logger.error("Bedrock API 호출 실패: %s", str(e))
            raise BedrockError(f"AI 서비스 호출에 실패했습니다: {str(e)}")

    async def converse_with_image(
        self,
        system_prompt: str,
        image_bytes: bytes,
        content_type: str,
        user_message: str = "이 영수증의 내용을 분석해주세요.",
        max_tokens: int = 4096,
    ) -> str:
        """Bedrock Converse API 호출 (이미지 포함 멀티모달)."""
        # content_type에서 media_type 추출 (image/jpeg → jpeg)
        media_type = content_type.split("/")[-1]
        if media_type == "jpg":
            media_type = "jpeg"

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": media_type,
                            "source": {"bytes": image_bytes},
                        }
                    },
                    {"text": user_message},
                ],
            }
        ]

        try:
            response = await asyncio.to_thread(
                self._client.converse,
                modelId=self._model_id,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={"maxTokens": max_tokens},
            )
            return response["output"]["message"]["content"][0]["text"]
        except Exception as e:
            logger.error("Bedrock Vision API 호출 실패: %s", str(e))
            raise BedrockError(f"AI 서비스 호출에 실패했습니다: {str(e)}")
