"""
타임존 유틸리티 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 타임존 변환의 핵심 속성을 검증한다.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.utils.timezone_utils import (
    KST,
    date_to_utc_range,
    ensure_utc_iso,
    parse_date_param,
)


# ---------------------------------------------------------------------------
# 테스트용 전략(Strategy) 정의
# ---------------------------------------------------------------------------

# 유효한 날짜 전략 (1970-01-01 ~ 2099-12-31 범위)
valid_date_strategy = st.dates(
    min_value=date(1970, 1, 1),
    max_value=date(2099, 12, 31),
)

# 타임존 오프셋 전략 (UTC-12 ~ UTC+14 범위, 실제 존재하는 오프셋 범위)
tz_offset_strategy = st.integers(min_value=-12, max_value=14).map(
    lambda h: timezone(timedelta(hours=h))
)

# naive datetime 전략
naive_datetime_strategy = st.datetimes(
    min_value=datetime(1970, 1, 1),
    max_value=datetime(2099, 12, 31, 23, 59, 59),
)

# aware datetime 전략 (다양한 타임존 오프셋 포함)
aware_datetime_strategy = st.builds(
    lambda dt, tz: dt.replace(tzinfo=tz),
    naive_datetime_strategy,
    tz_offset_strategy,
)


# ---------------------------------------------------------------------------
# Property 7: 날짜 파라미터 파싱 및 UTC 변환
# Feature: frontend-integration-improvements, Property 7: 날짜 파라미터 파싱 및 UTC 변환
# **Validates: Requirements 4.2, 4.3**
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(d=valid_date_strategy)
def test_parse_date_param_yyyy_mm_dd_returns_kst_midnight_utc(d: date):
    """임의의 유효한 날짜에 대해, YYYY-MM-DD 형식으로 parse_date_param에 전달하면
    KST 자정(해당 날짜 00:00 KST = 전날 15:00 UTC)에 해당하는 UTC datetime을 반환해야 한다.
    """
    value = d.isoformat()  # YYYY-MM-DD 형식
    result = parse_date_param(value)

    # 결과는 UTC 타임존이어야 한다
    assert result.tzinfo == timezone.utc, f"결과 타임존이 UTC가 아님: {result.tzinfo}"

    # KST 자정을 UTC로 변환한 기대값 계산
    kst_midnight = datetime(d.year, d.month, d.day, tzinfo=KST)
    expected_utc = kst_midnight.astimezone(timezone.utc)

    assert result == expected_utc, f"UTC 변환 불일치: {result} != {expected_utc}"

    # KST 자정은 UTC 전날 15:00이어야 한다
    assert result.hour == 15, f"UTC 시간이 15시가 아님: {result.hour}"


@settings(max_examples=30, deadline=None)
@given(dt=aware_datetime_strategy)
def test_parse_date_param_iso8601_with_offset_returns_utc(dt: datetime):
    """임의의 유효한 ISO 8601 형식(타임존 오프셋 포함) 문자열에 대해,
    parse_date_param은 해당 오프셋을 적용한 UTC datetime을 반환해야 한다.
    """
    value = dt.isoformat()
    result = parse_date_param(value)

    # 결과는 UTC 타임존이어야 한다
    assert result.tzinfo == timezone.utc, f"결과 타임존이 UTC가 아님: {result.tzinfo}"

    # 원본 datetime을 UTC로 변환한 기대값과 일치해야 한다
    expected_utc = dt.astimezone(timezone.utc)

    assert result == expected_utc, f"UTC 변환 불일치: {result} != {expected_utc}"


# ---------------------------------------------------------------------------
# Property 8: date_to_utc_range 24시간 범위
# Feature: frontend-integration-improvements, Property 8: date_to_utc_range 24시간 범위
# **Validates: Requirements 4.4**
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(d=valid_date_strategy, tz=tz_offset_strategy)
def test_date_to_utc_range_exactly_24_hours(d: date, tz: timezone):
    """임의의 날짜와 타임존 오프셋에 대해, date_to_utc_range가 반환하는
    (start_utc, end_utc) 범위는 정확히 24시간(86400초)이어야 한다.
    """
    start_utc, end_utc = date_to_utc_range(d, tz)

    # 범위가 정확히 86400초(24시간)여야 한다
    diff = (end_utc - start_utc).total_seconds()
    assert diff == 86400, f"범위가 86400초가 아님: {diff}초"


@settings(max_examples=30, deadline=None)
@given(d=valid_date_strategy, tz=tz_offset_strategy)
def test_date_to_utc_range_start_matches_midnight(d: date, tz: timezone):
    """임의의 날짜와 타임존 오프셋에 대해, date_to_utc_range의 start_utc는
    해당 날짜의 해당 타임존 자정을 UTC로 변환한 값과 일치해야 한다.
    """
    start_utc, _ = date_to_utc_range(d, tz)

    # 해당 타임존 기준 자정의 UTC 변환값 계산
    local_midnight = datetime(d.year, d.month, d.day, tzinfo=tz)
    expected_start = local_midnight.astimezone(timezone.utc)

    assert start_utc == expected_start, (
        f"start_utc 불일치: {start_utc} != {expected_start}"
    )


@settings(max_examples=30, deadline=None)
@given(d=valid_date_strategy)
def test_date_to_utc_range_default_kst(d: date):
    """tz_offset이 None이면 KST(UTC+09:00) 기준으로 동작해야 한다."""
    start_default, end_default = date_to_utc_range(d)
    start_kst, end_kst = date_to_utc_range(d, KST)

    assert start_default == start_kst, "기본값이 KST와 다름"
    assert end_default == end_kst, "기본값이 KST와 다름"


# ---------------------------------------------------------------------------
# Property 9: UTC ISO 8601 출력 형식
# Feature: frontend-integration-improvements, Property 9: UTC ISO 8601 출력 형식
# **Validates: Requirements 4.5**
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(dt=naive_datetime_strategy)
def test_ensure_utc_iso_ends_with_z_naive(dt: datetime):
    """임의의 naive datetime 객체에 대해, ensure_utc_iso가 반환하는 문자열은
    'Z'로 끝나야 한다.
    """
    result = ensure_utc_iso(dt)
    assert result.endswith("Z"), f"Z 접미사 누락: {result}"


@settings(max_examples=30, deadline=None)
@given(dt=aware_datetime_strategy)
def test_ensure_utc_iso_ends_with_z_aware(dt: datetime):
    """임의의 aware datetime 객체에 대해, ensure_utc_iso가 반환하는 문자열은
    'Z'로 끝나야 한다.
    """
    result = ensure_utc_iso(dt)
    assert result.endswith("Z"), f"Z 접미사 누락: {result}"


@settings(max_examples=30, deadline=None)
@given(dt=naive_datetime_strategy)
def test_ensure_utc_iso_round_trip_naive(dt: datetime):
    """임의의 naive datetime 객체에 대해, ensure_utc_iso 결과를 다시 파싱하면
    원본 datetime의 UTC 값과 동일해야 한다 (라운드 트립).
    """
    result_str = ensure_utc_iso(dt)

    # Z를 +00:00으로 치환하여 파싱
    parsed = datetime.fromisoformat(result_str.replace("Z", "+00:00"))

    # naive datetime은 UTC로 간주하므로 원본에 UTC를 부여한 값과 비교
    expected = dt.replace(tzinfo=timezone.utc, microsecond=0)

    assert parsed == expected, f"라운드 트립 불일치: {parsed} != {expected}"


@settings(max_examples=30, deadline=None)
@given(dt=aware_datetime_strategy)
def test_ensure_utc_iso_round_trip_aware(dt: datetime):
    """임의의 aware datetime 객체에 대해, ensure_utc_iso 결과를 다시 파싱하면
    원본 datetime의 UTC 값과 동일해야 한다 (라운드 트립).
    """
    result_str = ensure_utc_iso(dt)

    # Z를 +00:00으로 치환하여 파싱
    parsed = datetime.fromisoformat(result_str.replace("Z", "+00:00"))

    # 원본을 UTC로 변환한 값과 비교 (마이크로초는 strftime에서 제거됨)
    expected = dt.astimezone(timezone.utc).replace(microsecond=0)

    assert parsed == expected, f"라운드 트립 불일치: {parsed} != {expected}"
