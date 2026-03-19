"""타임존 변환 유틸리티 모듈.

UTC/KST 간 변환 및 날짜 범위 계산을 담당한다.
"""

from datetime import date, datetime, timedelta, timezone

# 한국 표준시 (UTC+09:00)
KST = timezone(timedelta(hours=9))


def date_to_utc_range(
    target_date: date,
    tz_offset: timezone | None = None,
) -> tuple[datetime, datetime]:
    """특정 날짜를 해당 타임존 기준 자정~익일 자정의 UTC 범위로 변환한다.

    tz_offset이 None이면 KST(UTC+09:00) 기준.

    Args:
        target_date: 대상 날짜
        tz_offset: 타임존 오프셋 (None이면 KST)

    Returns:
        (start_utc, end_utc) — start_utc <= t < end_utc, 정확히 86400초 범위
    """
    if tz_offset is None:
        tz_offset = KST

    # 해당 타임존 기준 자정
    local_midnight = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        tzinfo=tz_offset,
    )

    # UTC로 변환
    start_utc = local_midnight.astimezone(timezone.utc)
    end_utc = start_utc + timedelta(days=1)

    return start_utc, end_utc


def parse_date_param(value: str) -> datetime:
    """날짜 파라미터를 파싱하여 UTC datetime으로 변환한다.

    - YYYY-MM-DD (타임존 없음): KST 자정으로 해석 후 UTC 변환
    - ISO 8601 (타임존 오프셋 포함): 해당 오프셋을 적용하여 UTC 변환

    Args:
        value: 날짜 문자열 (YYYY-MM-DD 또는 ISO 8601)

    Returns:
        UTC datetime 객체

    Raises:
        ValueError: 파싱할 수 없는 형식인 경우
    """
    # ISO 8601 형식 시도 (타임존 오프셋 포함)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            # 타임존 정보가 있으면 UTC로 변환
            return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    # YYYY-MM-DD 형식 시도
    try:
        d = date.fromisoformat(value)
        # KST 자정으로 해석 후 UTC 변환
        kst_midnight = datetime(d.year, d.month, d.day, tzinfo=KST)
        return kst_midnight.astimezone(timezone.utc)
    except ValueError:
        pass

    raise ValueError(f"파싱할 수 없는 날짜 형식입니다: {value}")


def parse_date_param_to_date(value: str) -> date:
    """날짜 파라미터를 파싱하여 KST 기준 date 객체로 변환한다.

    - YYYY-MM-DD (타임존 없음): 그대로 date 객체 반환
    - ISO 8601 (타임존 오프셋 포함): KST로 변환 후 date 추출

    DB의 DATE 컬럼과 비교할 때 사용한다.

    Args:
        value: 날짜 문자열 (YYYY-MM-DD 또는 ISO 8601)

    Returns:
        KST 기준 date 객체

    Raises:
        ValueError: 파싱할 수 없는 형식인 경우
    """
    # YYYY-MM-DD 형식 시도 (타임존 없음 → KST 기준으로 해석)
    try:
        d = date.fromisoformat(value)
        return d
    except ValueError:
        pass

    # ISO 8601 형식 시도 (타임존 오프셋 포함 → KST로 변환 후 date 추출)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            kst_dt = dt.astimezone(KST)
            return kst_dt.date()
    except ValueError:
        pass

    raise ValueError(f"파싱할 수 없는 날짜 형식입니다: {value}")


def ensure_utc_iso(dt: datetime) -> str:
    """datetime을 ISO 8601 UTC 문자열(Z 접미사)로 변환한다.

    Args:
        dt: 변환할 datetime 객체 (naive이면 UTC로 간주)

    Returns:
        ISO 8601 UTC 문자열 (예: '2024-01-15T15:00:00Z')
    """
    if dt.tzinfo is None:
        # naive datetime은 UTC로 간주
        utc_dt = dt.replace(tzinfo=timezone.utc)
    else:
        # 타임존 정보가 있으면 UTC로 변환
        utc_dt = dt.astimezone(timezone.utc)

    # isoformat()에서 +00:00 대신 Z 접미사 사용
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
