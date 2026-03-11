"""
날짜 파싱 유틸리티 단위 테스트.

공통 모듈 app/utils/date_utils.py의 safe_parse_date 함수를 검증한다.
DB 세션이 필요 없는 순수 단위 테스트.

Validates: Requirements 1.3, 1.4, 1.5
"""

from datetime import date

import pytest

from app.utils.date_utils import safe_parse_date


# 공통 모듈의 safe_parse_date 함수를 테스트
_parse_funcs = pytest.mark.parametrize(
    "parse_date",
    [safe_parse_date],
    ids=["date_utils"],
)


@_parse_funcs
class TestSafeParseDateValid:
    """유효한 날짜 문자열 파싱 검증.

    **Validates: Requirements 14.1, 14.2**
    """

    def test_valid_date_string(self, parse_date):
        """유효한 날짜 문자열 "2025-01-15"를 date 객체로 파싱한다."""
        result = parse_date("2025-01-15")
        assert result == date(2025, 1, 15)


@_parse_funcs
class TestSafeParseDateInvalid:
    """유효하지 않은 입력 시 오늘 날짜 반환 검증.

    **Validates: Requirements 14.3, 14.4**
    """

    def test_invalid_string_returns_today(self, parse_date):
        """유효하지 않은 문자열 "invalid" 입력 시 오늘 날짜를 반환한다."""
        result = parse_date("invalid")
        assert result == date.today()

    def test_empty_string_returns_today(self, parse_date):
        """빈 문자열 "" 입력 시 오늘 날짜를 반환한다."""
        result = parse_date("")
        assert result == date.today()


@_parse_funcs
class TestSafeParseDateNone:
    """None 입력 시 오늘 날짜 반환 검증.

    **Validates: Requirements 14.5, 14.6**
    """

    def test_none_returns_today(self, parse_date):
        """None 입력 시 오늘 날짜를 반환한다."""
        result = parse_date(None)
        assert result == date.today()


@_parse_funcs
class TestSafeParseDateObject:
    """date 객체 입력 시 그대로 반환 검증.

    **Validates: Requirements 14.1, 14.2**
    """

    def test_date_object_returns_same(self, parse_date):
        """date 객체 입력 시 동일한 date 객체를 그대로 반환한다."""
        input_date = date(2025, 3, 1)
        result = parse_date(input_date)
        assert result == date(2025, 3, 1)
