"""
isinstance Enum 판별 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 MoneyLog Enum 인스턴스에 대한
isinstance 판별 정확성을 검증한다.
hasattr(v, "value") 패턴 대신 isinstance(v, Enum) 검사가
정확한 판별을 보장하는지 확인한다.
"""

from enum import Enum

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.enums import (
    Area,
    AssetType,
    CarType,
    CeremonyDirection,
    CeremonyEventType,
    FeedbackType,
    GoalStatus,
    GoalType,
    GroupRole,
    MessageRole,
    Ownership,
    OwnerType,
    ScanStatus,
    SubscriptionCategory,
    SubscriptionCycle,
    SubscriptionStatus,
    TransactionSource,
    TransactionType,
)

# ---------------------------------------------------------------------------
# MoneyLog에서 사용하는 모든 Enum 클래스 목록
# ---------------------------------------------------------------------------
_ALL_ENUM_CLASSES = [
    Area,
    AssetType,
    CarType,
    CeremonyDirection,
    CeremonyEventType,
    FeedbackType,
    GoalStatus,
    GoalType,
    GroupRole,
    MessageRole,
    Ownership,
    OwnerType,
    ScanStatus,
    SubscriptionCategory,
    SubscriptionCycle,
    SubscriptionStatus,
    TransactionSource,
    TransactionType,
]

# 모든 Enum 인스턴스를 하나의 리스트로 수집
_ALL_ENUM_INSTANCES = [member for cls in _ALL_ENUM_CLASSES for member in cls]

# 비-Enum 값 전략: Enum이 아닌 다양한 타입의 값 생성
_NON_ENUM_VALUES = st.one_of(
    st.integers(),
    st.floats(allow_nan=True),
    st.text(),
    st.none(),
    st.booleans(),
    st.lists(st.integers(), max_size=3),
    st.binary(max_size=10),
)


# ---------------------------------------------------------------------------
# Property 4: isinstance Enum 판별 정확성
# Feature: python-best-practices-improvements, Property 4: isinstance Enum 판별 정확성
# MoneyLog Enum 인스턴스에 대해 isinstance(e, Enum) == True,
# 비-Enum 값에 대해 False
# **Validates: 요구사항 2.4**
# ---------------------------------------------------------------------------


@settings(max_examples=30)
@given(enum_instance=st.sampled_from(_ALL_ENUM_INSTANCES))
def test_isinstance_returns_true_for_enum_instances(enum_instance):
    """
    임의의 MoneyLog Enum 인스턴스에 대해
    isinstance(e, Enum)은 항상 True를 반환해야 한다.
    이는 hasattr(v, "value") 패턴보다 정확한 타입 판별을 보장한다.
    """
    assert isinstance(enum_instance, Enum) is True


@settings(max_examples=30)
@given(value=_NON_ENUM_VALUES)
def test_isinstance_returns_false_for_non_enum_values(value):
    """
    임의의 비-Enum 값(int, str, list 등)에 대해
    isinstance(v, Enum)은 항상 False를 반환해야 한다.
    참고: hasattr(v, "value") 패턴은 "value" 속성을 가진 비-Enum 객체에서
    잘못된 True를 반환할 수 있으므로 isinstance가 더 정확하다.
    """
    assert isinstance(value, Enum) is False
