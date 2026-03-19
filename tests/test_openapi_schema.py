"""
OpenAPI 스키마 Enum 검증 단위 테스트.

FastAPI 앱의 OpenAPI 스키마에서 Enum 관련 정의를 검증한다:
- 주요 Enum 타입이 components/schemas에 존재하는지 확인
- 각 Enum 스키마에 title, description 속성이 존재하는지 확인
- Enum 스키마에 enum 배열이 올바른 값을 포함하는지 확인

Requirements: 2.2, 2.4
"""

import pytest

from app.main import app
from app.models.enums import (
    Area,
    AssetType,
    CarType,
    CeremonyDirection,
    CeremonyEventType,
    FeedbackType,
    GoalStatus,
    GoalType,
    Ownership,
    SubscriptionCategory,
    SubscriptionCycle,
    SubscriptionStatus,
    TransactionType,
)


# ---------------------------------------------------------------------------
# OpenAPI 스키마에 직접 노출되는 Enum 목록
# (API 엔드포인트의 요청/응답 스키마에서 사용되는 Enum만 포함)
# ---------------------------------------------------------------------------

_EXPOSED_ENUMS: dict[str, type] = {
    "Area": Area,
    "TransactionType": TransactionType,
    "CarType": CarType,
    "CeremonyDirection": CeremonyDirection,
    "CeremonyEventType": CeremonyEventType,
    "Ownership": Ownership,
    "AssetType": AssetType,
    "SubscriptionCategory": SubscriptionCategory,
    "SubscriptionCycle": SubscriptionCycle,
    "SubscriptionStatus": SubscriptionStatus,
    "GoalType": GoalType,
    "GoalStatus": GoalStatus,
    "FeedbackType": FeedbackType,
}


@pytest.fixture(scope="module")
def openapi_schemas() -> dict:
    """OpenAPI 스키마의 components/schemas를 반환한다."""
    schema = app.openapi()
    return schema["components"]["schemas"]


# ---------------------------------------------------------------------------
# 1. Enum 타입이 OpenAPI 스키마에 존재하는지 확인
# ---------------------------------------------------------------------------


class TestEnumExistence:
    """OpenAPI 스키마에 주요 Enum 타입이 존재하는지 검증한다."""

    @pytest.mark.parametrize("enum_name", list(_EXPOSED_ENUMS.keys()))
    def test_enum_exists_in_schema(self, openapi_schemas: dict, enum_name: str):
        """각 Enum 타입이 components/schemas에 정의되어 있어야 한다."""
        assert enum_name in openapi_schemas, (
            f"{enum_name}이 OpenAPI 스키마의 components/schemas에 존재하지 않습니다"
        )


# ---------------------------------------------------------------------------
# 2. 각 Enum 스키마에 title과 description이 존재하는지 확인
# ---------------------------------------------------------------------------


class TestEnumTitleDescription:
    """OpenAPI 스키마의 Enum 정의에 title과 description이 존재하는지 검증한다.

    Validates: Requirements 2.2
    """

    @pytest.mark.parametrize("enum_name", list(_EXPOSED_ENUMS.keys()))
    def test_enum_has_title(self, openapi_schemas: dict, enum_name: str):
        """각 Enum 스키마에 title 속성이 존재해야 한다."""
        enum_schema = openapi_schemas[enum_name]
        assert "title" in enum_schema, (
            f"{enum_name} 스키마에 title 속성이 없습니다"
        )
        assert len(enum_schema["title"].strip()) > 0, (
            f"{enum_name} 스키마의 title이 비어있습니다"
        )

    @pytest.mark.parametrize("enum_name", list(_EXPOSED_ENUMS.keys()))
    def test_enum_has_description(self, openapi_schemas: dict, enum_name: str):
        """각 Enum 스키마에 description 속성이 존재해야 한다."""
        enum_schema = openapi_schemas[enum_name]
        assert "description" in enum_schema, (
            f"{enum_name} 스키마에 description 속성이 없습니다"
        )
        assert len(enum_schema["description"].strip()) > 0, (
            f"{enum_name} 스키마의 description이 비어있습니다"
        )


# ---------------------------------------------------------------------------
# 3. Enum 스키마에 enum 배열이 올바른 값을 포함하는지 확인
# ---------------------------------------------------------------------------


class TestEnumValues:
    """OpenAPI 스키마의 Enum 정의에 올바른 enum 배열이 포함되는지 검증한다.

    Validates: Requirements 2.2, 2.4
    """

    @pytest.mark.parametrize(
        "enum_name,enum_cls",
        list(_EXPOSED_ENUMS.items()),
    )
    def test_enum_has_values_array(
        self, openapi_schemas: dict, enum_name: str, enum_cls: type
    ):
        """각 Enum 스키마에 enum 배열이 존재해야 한다."""
        enum_schema = openapi_schemas[enum_name]
        assert "enum" in enum_schema, (
            f"{enum_name} 스키마에 enum 배열이 없습니다"
        )

    @pytest.mark.parametrize(
        "enum_name,enum_cls",
        list(_EXPOSED_ENUMS.items()),
    )
    def test_enum_values_match(
        self, openapi_schemas: dict, enum_name: str, enum_cls: type
    ):
        """각 Enum 스키마의 enum 배열이 Python Enum 클래스의 값과 일치해야 한다."""
        enum_schema = openapi_schemas[enum_name]
        expected_values = [member.value for member in enum_cls]
        actual_values = enum_schema["enum"]
        assert actual_values == expected_values, (
            f"{enum_name}의 enum 값이 일치하지 않습니다. "
            f"기대: {expected_values}, 실제: {actual_values}"
        )


# ---------------------------------------------------------------------------
# 4. OpenAPI 스키마 전체 구조 검증
# ---------------------------------------------------------------------------


class TestOpenAPISchemaStructure:
    """OpenAPI 스키마의 전체 구조를 검증한다.

    Validates: Requirements 2.4
    """

    def test_openapi_schema_has_components(self):
        """OpenAPI 스키마에 components 섹션이 존재해야 한다."""
        schema = app.openapi()
        assert "components" in schema, "OpenAPI 스키마에 components가 없습니다"
        assert "schemas" in schema["components"], (
            "OpenAPI 스키마에 components/schemas가 없습니다"
        )

    def test_enum_schemas_have_string_type(self, openapi_schemas: dict):
        """모든 Enum 스키마의 type이 string이어야 한다."""
        for enum_name in _EXPOSED_ENUMS:
            enum_schema = openapi_schemas[enum_name]
            assert enum_schema.get("type") == "string", (
                f"{enum_name} 스키마의 type이 'string'이 아닙니다: "
                f"{enum_schema.get('type')}"
            )
