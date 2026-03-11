"""날짜 파싱 공통 유틸리티 모듈."""

from datetime import date


def safe_parse_date(value) -> date:
    """date 객체 또는 문자열을 안전하게 date로 변환한다. 실패 시 오늘 날짜 반환."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            pass
    return date.today()
