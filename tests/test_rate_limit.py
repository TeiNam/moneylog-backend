"""
Rate Limiter 단위 테스트.

SlidingWindowRateLimiter 클래스와 rate_limit_dependency 함수의
핵심 동작을 검증한다.

Requirements: 2.4
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import RateLimitExceededError
from app.core.rate_limit import SlidingWindowRateLimiter, rate_limit_dependency


class TestSlidingWindowRateLimiter:
    """SlidingWindowRateLimiter 클래스 단위 테스트."""

    def test_allows_requests_within_limit(self) -> None:
        """임계값 이내의 요청은 모두 허용된다."""
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed("192.168.1.1") is True
        assert limiter.is_allowed("192.168.1.1") is True
        assert limiter.is_allowed("192.168.1.1") is True

    def test_blocks_requests_exceeding_limit(self) -> None:
        """임계값을 초과하는 요청은 거부된다."""
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is True
        # 3번째 요청은 거부
        assert limiter.is_allowed("10.0.0.1") is False

    def test_different_ips_are_independent(self) -> None:
        """서로 다른 IP는 독립적으로 카운팅된다."""
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.2") is True
        # 각 IP의 2번째 요청은 거부
        assert limiter.is_allowed("10.0.0.1") is False
        assert limiter.is_allowed("10.0.0.2") is False

    def test_sliding_window_expires_old_requests(self) -> None:
        """윈도우가 지나면 오래된 요청이 만료되어 다시 허용된다."""
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=1)
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.1") is False

        # 윈도우 시간이 지난 후에는 다시 허용
        future_time = time.time() + 2
        limiter._cleanup("10.0.0.1", future_time)

        # cleanup 후 다시 요청 가능
        assert limiter.is_allowed("10.0.0.1") is True


class TestRateLimitDependency:
    """rate_limit_dependency 함수 테스트."""

    @pytest.mark.asyncio
    async def test_allows_normal_request(self) -> None:
        """정상 요청은 통과시킨다."""
        mock_limiter = MagicMock(spec=SlidingWindowRateLimiter)
        mock_limiter.is_allowed.return_value = True

        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"

        with patch("app.core.rate_limit._get_limiter", return_value=mock_limiter):
            # 예외 없이 정상 통과
            await rate_limit_dependency(mock_request)

        mock_limiter.is_allowed.assert_called_once_with("192.168.1.1")

    @pytest.mark.asyncio
    async def test_raises_on_rate_limit_exceeded(self) -> None:
        """임계값 초과 시 RateLimitExceededError를 발생시킨다."""
        mock_limiter = MagicMock(spec=SlidingWindowRateLimiter)
        mock_limiter.is_allowed.return_value = False

        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"

        with patch("app.core.rate_limit._get_limiter", return_value=mock_limiter):
            with pytest.raises(RateLimitExceededError) as exc_info:
                await rate_limit_dependency(mock_request)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_handles_missing_client(self) -> None:
        """client가 None인 경우 'unknown' 키로 처리한다."""
        mock_limiter = MagicMock(spec=SlidingWindowRateLimiter)
        mock_limiter.is_allowed.return_value = True

        mock_request = MagicMock()
        mock_request.client = None

        with patch("app.core.rate_limit._get_limiter", return_value=mock_limiter):
            await rate_limit_dependency(mock_request)

        mock_limiter.is_allowed.assert_called_once_with("unknown")


class TestRateLimitExceededError:
    """RateLimitExceededError 예외 클래스 테스트."""

    def test_default_message(self) -> None:
        """기본 에러 메시지와 상태 코드를 확인한다."""
        error = RateLimitExceededError()
        assert error.status_code == 429
        assert "요청이 너무 많습니다" in error.detail

    def test_custom_message(self) -> None:
        """커스텀 에러 메시지를 확인한다."""
        error = RateLimitExceededError(detail="커스텀 메시지")
        assert error.status_code == 429
        assert error.detail == "커스텀 메시지"
