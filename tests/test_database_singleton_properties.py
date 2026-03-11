"""
데이터베이스 싱글턴 동일성 속성 기반 테스트.

Feature: python-best-practices-improvements, Property 8: 엔진 싱글턴 동일성
"""

from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Property 8: 엔진 싱글턴 동일성
# N회 get_engine() 호출 시 모두 동일한 객체 반환
# **Validates: 요구사항 5.5**
# ---------------------------------------------------------------------------


@settings(max_examples=30)
@given(n=st.integers(min_value=2, max_value=10))
def test_get_engine_returns_same_instance(n: int):
    """
    임의의 횟수 N(N >= 2)만큼 get_engine()을 호출하면,
    모든 호출이 동일한 객체(id()가 같은)를 반환해야 한다.

    **Validates: 요구사항 5.5**
    """
    from app.core.database import _DatabaseManager

    # 테스트마다 새 매니저 인스턴스로 격리
    manager = _DatabaseManager()

    mock_settings = MagicMock()
    mock_settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    mock_settings.DEBUG = False

    # create_async_engine도 모킹하여 실제 엔진 생성 방지
    mock_engine = MagicMock()

    with (
        patch("app.core.database.get_settings", return_value=mock_settings),
        patch("app.core.database.create_async_engine", return_value=mock_engine),
    ):
        engines = [manager.get_engine() for _ in range(n)]

    # 모든 호출이 동일한 객체를 반환하는지 검증
    first_id = id(engines[0])
    for i, engine in enumerate(engines):
        assert id(engine) == first_id, (
            f"{i+1}번째 호출의 엔진 id가 다름: {id(engine)} != {first_id}"
        )
