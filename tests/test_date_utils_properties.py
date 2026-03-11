"""
safe_parse_date 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 날짜 파싱 유틸리티의 핵심 속성을 검증한다.
"""

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from app.utils.date_utils import safe_parse_date


# ---------------------------------------------------------------------------
# Property 1: date 객체 멱등성
# safe_parse_date(d) == d — 모든 유효한 date 객체에 대해 원본을 그대로 반환
# **Validates: 요구사항 1.3, 1.6**
# ---------------------------------------------------------------------------


@settings(max_examples=30)
@given(d=st.dates())
def test_safe_parse_date_idempotent_for_date_objects(d: date):
    """
    임의의 date 객체를 safe_parse_date에 전달하면
    항상 동일한 date 객체를 반환해야 한다 (멱등성).
    """
    result = safe_parse_date(d)
    assert result == d


# ---------------------------------------------------------------------------
# Property 2: ISO 문자열 라운드트립
# safe_parse_date(d.isoformat()) == d — ISO 형식 문자열을 파싱하면 원본 date 복원
# **Validates: 요구사항 1.4**
# ---------------------------------------------------------------------------


@settings(max_examples=30)
@given(d=st.dates())
def test_safe_parse_date_iso_string_roundtrip(d: date):
    """
    임의의 date 객체를 ISO 문자열로 변환한 뒤 safe_parse_date에 전달하면
    원본 date 객체와 동일한 결과를 반환해야 한다 (라운드트립).
    """
    iso_str = d.isoformat()
    result = safe_parse_date(iso_str)
    assert result == d


# ---------------------------------------------------------------------------
# Property 3: 잘못된 입력 폴백
# date도 아니고 유효한 ISO 문자열도 아닌 값에 대해 date.today() 반환
# **Validates: 요구사항 1.5**
# ---------------------------------------------------------------------------


def _is_valid_iso_date(s: str) -> bool:
    """문자열이 유효한 ISO 날짜 형식인지 확인하는 헬퍼 함수."""
    try:
        date.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False


# 유효하지 않은 입력 전략: date가 아니고 유효한 ISO 날짜 문자열도 아닌 값
_invalid_inputs = st.one_of(
    st.integers(),                          # 정수
    st.floats(allow_nan=True),              # 부동소수점
    st.none(),                              # None
    st.lists(st.integers(), max_size=3),    # 리스트
    st.text().filter(lambda s: not _is_valid_iso_date(s)),  # 유효하지 않은 문자열
)


@settings(max_examples=30)
@given(value=_invalid_inputs)
def test_safe_parse_date_invalid_input_returns_today(value):
    """
    date 객체도 아니고 유효한 ISO 날짜 문자열도 아닌 값을 전달하면
    항상 오늘 날짜(date.today())를 반환해야 한다.
    """
    result = safe_parse_date(value)
    assert result == date.today()
