"""
메타데이터 제거 멱등성 속성 기반 테스트.

Feature: python-best-practices-improvements, Property 9: 메타데이터 제거 멱등성
"""

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Property 9: 메타데이터 제거 멱등성
# 1회 vs N회 호출 후 Base.metadata 상태 동일
# **Validates: 요구사항 6.3**
# ---------------------------------------------------------------------------


def _snapshot_metadata():
    """현재 Base.metadata의 테이블별 schema와 컬럼 타입 스냅샷을 반환한다."""
    from app.models.base import Base

    snapshot = {}
    for name, table in Base.metadata.tables.items():
        cols = {c.name: type(c.type).__name__ for c in table.columns}
        snapshot[name] = {"schema": table.schema, "columns": cols}
    return snapshot


@settings(max_examples=30)
@given(n=st.integers(min_value=2, max_value=5))
def test_remove_schema_from_metadata_is_idempotent(n: int):
    """
    임의의 횟수 N(N >= 2)만큼 _remove_schema_from_metadata()를 호출한 후의
    Base.metadata 상태는, 1회 호출 후의 상태와 동일해야 한다.

    **Validates: 요구사항 6.3**
    """
    import tests.conftest as conftest_mod

    # 가드 플래그를 리셋하여 실제 실행이 되도록 함
    conftest_mod._metadata_cleaned = False

    # 1회 호출 후 스냅샷
    conftest_mod._remove_schema_from_metadata()
    snapshot_after_one = _snapshot_metadata()

    # 가드 플래그 리셋 후 N회 추가 호출
    for _ in range(n):
        conftest_mod._metadata_cleaned = False
        conftest_mod._remove_schema_from_metadata()

    snapshot_after_n = _snapshot_metadata()

    # 1회 호출 후와 N회 호출 후 상태가 동일해야 한다
    assert snapshot_after_one == snapshot_after_n, (
        f"1회 호출 후와 {n+1}회 호출 후 메타데이터 상태가 다름"
    )
