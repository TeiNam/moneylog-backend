"""
Enum 스키마 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 OpenAPI 스키마에서
Enum 타입의 title/description 존재 여부를 검증한다.

Feature: frontend-integration-improvements, Property 4: Enum title/description 존재
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
    TransactionType,
)
from app.schemas.enums import ENUM_METADATA


# ---------------------------------------------------------------------------
# 프로젝트에서 사용하는 모든 Enum 클래스 목록 (17개)
# ---------------------------------------------------------------------------

_ALL_ENUM_CLASSES: list[type[Enum]] = [
    Area,
    TransactionType,
    CarType,
    CeremonyDirection,
    CeremonyEventType,
    OwnerType,
    Ownership,
    AssetType,
    GroupRole,
    SubscriptionCategory,
    SubscriptionCycle,
    SubscriptionStatus,
    GoalType,
    GoalStatus,
    MessageRole,
    ScanStatus,
    FeedbackType,
]


# ---------------------------------------------------------------------------
# Property 4: Enum title/description 존재
# Feature: frontend-integration-improvements, Property 4: Enum title/description 존재
# 임의의 프로젝트 내 Enum 타입에 대해, OpenAPI 스키마의 해당 Enum 정의에는
# title과 description 속성이 모두 존재해야 한다.
# **Validates: Requirements 2.2**
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(enum_cls=st.sampled_from(_ALL_ENUM_CLASSES))
def test_enum_has_doc_string(enum_cls: type[Enum]):
    """임의의 Enum 클래스에 대해 __doc__ 문서화 문자열이 존재하고
    비어있지 않아야 한다.

    **Validates: Requirements 2.2**
    """
    doc = enum_cls.__doc__
    assert doc is not None, f"{enum_cls.__name__}에 __doc__이 없습니다"
    assert len(doc.strip()) > 0, f"{enum_cls.__name__}의 __doc__이 비어있습니다"


@settings(max_examples=30, deadline=None)
@given(enum_cls=st.sampled_from(_ALL_ENUM_CLASSES))
def test_enum_has_metadata_title_and_description(enum_cls: type[Enum]):
    """임의의 Enum 클래스에 대해 ENUM_METADATA에 title과 description이
    모두 정의되어 있어야 한다.

    **Validates: Requirements 2.2**
    """
    assert enum_cls in ENUM_METADATA, (
        f"{enum_cls.__name__}이 ENUM_METADATA에 등록되지 않았습니다"
    )
    meta = ENUM_METADATA[enum_cls]
    assert "title" in meta, f"{enum_cls.__name__}에 title이 없습니다"
    assert "description" in meta, f"{enum_cls.__name__}에 description이 없습니다"
    assert len(meta["title"].strip()) > 0, (
        f"{enum_cls.__name__}의 title이 비어있습니다"
    )
    assert len(meta["description"].strip()) > 0, (
        f"{enum_cls.__name__}의 description이 비어있습니다"
    )


@settings(max_examples=30, deadline=None)
@given(enum_cls=st.sampled_from(_ALL_ENUM_CLASSES))
def test_enum_schema_exposes_enum_values(enum_cls: type[Enum]):
    """임의의 Enum 클래스에 대해 Pydantic JSON 스키마에서
    enum 배열이 올바르게 노출되어야 한다.

    **Validates: Requirements 2.2**
    """
    from pydantic import BaseModel, Field
    from app.schemas.enums import enum_field

    # 동적으로 Enum 필드를 가진 모델 생성
    model = type(
        "TestModel",
        (BaseModel,),
        {"__annotations__": {"value": enum_cls}, "value": enum_field(enum_cls)},
    )

    schema = model.model_json_schema()
    # Pydantic은 Enum을 $defs에 별도 정의하거나 인라인으로 포함할 수 있음
    # 두 경우 모두 enum 배열이 존재해야 함
    props = schema.get("properties", {})
    value_schema = props.get("value", {})

    # $ref가 있으면 $defs에서 찾기
    if "$ref" in value_schema:
        ref_name = value_schema["$ref"].split("/")[-1]
        defs = schema.get("$defs", {})
        value_schema = defs.get(ref_name, {})

    # allOf 패턴 처리 (json_schema_extra 사용 시)
    if "allOf" in value_schema:
        # allOf 내의 $ref에서 실제 Enum 정의를 찾기
        for item in value_schema["allOf"]:
            if "$ref" in item:
                ref_name = item["$ref"].split("/")[-1]
                defs = schema.get("$defs", {})
                ref_schema = defs.get(ref_name, {})
                # enum 배열 확인
                assert "enum" in ref_schema, (
                    f"{enum_cls.__name__}의 $defs 정의에 enum 배열이 없습니다"
                )
                expected_values = [m.value for m in enum_cls]
                assert ref_schema["enum"] == expected_values, (
                    f"{enum_cls.__name__}의 enum 값이 일치하지 않습니다"
                )
                return

    # 직접 enum 배열 확인
    assert "enum" in value_schema, (
        f"{enum_cls.__name__}의 스키마에 enum 배열이 없습니다: {value_schema}"
    )
    expected_values = [m.value for m in enum_cls]
    assert value_schema["enum"] == expected_values, (
        f"{enum_cls.__name__}의 enum 값이 일치하지 않습니다"
    )
