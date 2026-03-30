"""
인메모리 슬라이딩 윈도우 Rate Limiter.

IP 기반으로 요청 빈도를 제한하여 브루트포스 공격을 방어한다.
FastAPI 의존성(Depends)으로 사용할 수 있는 함수를 제공한다.
"""

import time
from collections import defaultdict

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceededError


class SlidingWindowRateLimiter:
    """인메모리 슬라이딩 윈도우 방식의 Rate Limiter.

    각 IP별로 요청 타임스탬프를 기록하고,
    윈도우 내 요청 수가 임계값을 초과하면 제한한다.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # IP → 요청 타임스탬프 리스트
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str, now: float) -> None:
        """윈도우 밖의 오래된 타임스탬프를 제거한다."""
        cutoff = now - self.window_seconds
        timestamps = self._requests[key]
        # 윈도우 내 타임스탬프만 유지
        self._requests[key] = [ts for ts in timestamps if ts > cutoff]

    def is_allowed(self, key: str) -> bool:
        """요청이 허용되는지 확인하고, 허용 시 타임스탬프를 기록한다."""
        now = time.time()
        self._cleanup(key, now)

        if len(self._requests[key]) >= self.max_requests:
            return False

        self._requests[key].append(now)
        return True


# 모듈 레벨 싱글턴 인스턴스 (설정에서 값을 읽어 초기화)
_limiter: SlidingWindowRateLimiter | None = None


def _get_limiter() -> SlidingWindowRateLimiter:
    """Rate Limiter 싱글턴 인스턴스를 반환한다."""
    global _limiter
    if _limiter is None:
        settings = get_settings()
        _limiter = SlidingWindowRateLimiter(
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )
    return _limiter


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI 의존성으로 사용하는 Rate Limit 검사 함수.

    클라이언트 IP를 기준으로 요청 빈도를 확인하고,
    임계값 초과 시 RateLimitExceededError를 발생시킨다.
    """
    limiter = _get_limiter()
    # 클라이언트 IP 추출 (프록시 뒤에서는 client.host가 None일 수 있음)
    client_ip = request.client.host if request.client else "unknown"

    if not limiter.is_allowed(client_ip):
        raise RateLimitExceededError()
