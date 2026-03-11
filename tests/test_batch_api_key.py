"""
배치 API 키 인증 단위 테스트.

app/core/dependencies.py의 verify_batch_api_key 함수를 직접 테스트한다.
유효한 API 키, 잘못된 API 키 케이스를 검증한다.

요구사항: 11.1, 11.2, 11.3
"""

from unittest.mock import patch, MagicMock

import pytest

from app.core.dependencies import verify_batch_api_key
from app.core.exceptions import ForbiddenError


def _mock_settings(batch_api_key: str = "test-secret-key") -> MagicMock:
    """테스트용 Settings mock 객체를 생성한다."""
    settings = MagicMock()
    settings.BATCH_API_KEY = batch_api_key
    return settings


# ══════════════════════════════════════════════
# 배치 API 키 인증 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_verify_batch_api_key_success():
    """유효한 API 키로 호출 시 정상 동작 검증. (요구사항 11.1)"""
    with patch(
        "app.core.dependencies.get_settings",
        return_value=_mock_settings("test-secret-key"),
    ):
        # 예외 없이 정상 완료되어야 함
        result = await verify_batch_api_key(x_api_key="test-secret-key")
        assert result is None


@pytest.mark.asyncio
async def test_verify_batch_api_key_invalid():
    """잘못된 API 키로 호출 시 ForbiddenError 검증. (요구사항 11.2)"""
    with patch(
        "app.core.dependencies.get_settings",
        return_value=_mock_settings("test-secret-key"),
    ):
        with pytest.raises(ForbiddenError, match="배치 실행 권한이 없습니다"):
            await verify_batch_api_key(x_api_key="wrong-key")


@pytest.mark.asyncio
async def test_verify_batch_api_key_empty_string():
    """빈 문자열 API 키로 호출 시 ForbiddenError 검증. (요구사항 11.2)"""
    with patch(
        "app.core.dependencies.get_settings",
        return_value=_mock_settings("test-secret-key"),
    ):
        with pytest.raises(ForbiddenError, match="배치 실행 권한이 없습니다"):
            await verify_batch_api_key(x_api_key="")
