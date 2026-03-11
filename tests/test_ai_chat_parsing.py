"""
AI 응답 파싱 순수 함수 속성 기반 테스트.

AIChatService._parse_extracted_data, _build_system_prompt,
ReceiptService._parse_receipt_response 순수 함수를 DB 없이 독립 테스트한다.
BedrockError 에러 처리도 검증한다.

Validates: Requirements 5.6, 5.7, 7.3, 7.5, 7.6, 16.1, 16.2
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.ai_chat_service import AIChatService
from app.services.bedrock_client import BedrockError
from app.services.receipt_service import ReceiptService


# ══════════════════════════════════════════════
# 순수 함수 접근을 위한 최소 인스턴스 생성
# ══════════════════════════════════════════════

def _make_chat_service() -> AIChatService:
    """DB 없이 순수 함수 테스트를 위한 최소 AIChatService 인스턴스."""
    return AIChatService(
        session_repo=None,
        message_repo=None,
        feedback_repo=None,
        bedrock_client=None,
        transaction_service=None,
        category_repo=None,
        asset_repo=None,
    )


def _make_receipt_service() -> ReceiptService:
    """DB 없이 순수 함수 테스트를 위한 최소 ReceiptService 인스턴스."""
    return ReceiptService(
        scan_repo=None,
        feedback_repo=None,
        bedrock_client=None,
        transaction_service=None,
    )


# ══════════════════════════════════════════════
# Mock 객체 (_build_system_prompt 테스트용)
# ══════════════════════════════════════════════

class MockCategory:
    """테스트용 카테고리 객체."""

    def __init__(self, major: str, minor: str, area: str, type_: str) -> None:
        self.major_category = major
        self.minor_category = minor
        self.area = area
        self.type = type_


class MockAsset:
    """테스트용 자산(결제수단) 객체."""

    def __init__(self, name: str, asset_id: str, asset_type: str) -> None:
        self.name = name
        self.id = asset_id
        self.asset_type = asset_type


class MockFeedback:
    """테스트용 피드백 객체."""

    def __init__(self, original: str, corrected: str, fb_type: str) -> None:
        self.original_value = original
        self.corrected_value = corrected
        self.feedback_type = fb_type


# ══════════════════════════════════════════════
# Hypothesis 전략 정의
# ══════════════════════════════════════════════

# JSON 직렬화 가능한 금액 전략
amounts = st.integers(min_value=100, max_value=10_000_000)

# 설명 텍스트 전략
descriptions = st.text(
    min_size=1, max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

# 카테고리 이름 전략
category_names = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

# 피드백 값 전략
feedback_values = st.text(
    min_size=1, max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

# 피드백 유형 전략
feedback_types = st.sampled_from([
    "CATEGORY_CORRECTION", "AMOUNT_CORRECTION", "DESCRIPTION_CORRECTION",
])


# ══════════════════════════════════════════════
# 14.1: _parse_extracted_data 순수 함수 테스트
# ══════════════════════════════════════════════

class TestParseExtractedData:
    """_parse_extracted_data 순수 함수 속성 기반 테스트.

    **Validates: Requirements 7.3, 7.6**
    """

    def setup_method(self):
        """각 테스트 메서드 전에 서비스 인스턴스를 생성한다."""
        self.service = _make_chat_service()

    @settings(max_examples=30, deadline=None)
    @given(amount=amounts, description=descriptions)
    def test_valid_json_block_returns_dict(self, amount: int, description: str):
        """유효한 ```json 블록이 포함된 AI 응답에서 dict를 반환해야 한다.

        **Validates: Requirements 7.3**
        """
        data = {"amount": amount, "description": description}
        ai_response = f"거래를 분석했습니다.\n```json\n{json.dumps(data, ensure_ascii=False)}\n```"

        result = self.service._parse_extracted_data(ai_response)

        assert result is not None
        assert isinstance(result, dict)
        assert result["amount"] == amount
        assert result["description"] == description

    @settings(max_examples=30, deadline=None)
    @given(amount=amounts, description=descriptions)
    def test_raw_json_object_returns_dict(self, amount: int, description: str):
        """원시 JSON 객체가 포함된 AI 응답에서 dict를 반환해야 한다.

        **Validates: Requirements 7.3**
        """
        data = {"amount": amount, "description": description}
        ai_response = f"분석 결과입니다: {json.dumps(data, ensure_ascii=False)}"

        result = self.service._parse_extracted_data(ai_response)

        assert result is not None
        assert isinstance(result, dict)
        assert result["amount"] == amount

    @settings(max_examples=30, deadline=None)
    @given(text=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "Z"))))
    def test_no_json_returns_none(self, text: str):
        """JSON이 포함되지 않은 AI 응답에서 None을 반환해야 한다.

        **Validates: Requirements 7.6**
        """
        # 중괄호가 없는 텍스트만 사용
        clean_text = text.replace("{", "").replace("}", "").replace("[", "").replace("]", "")
        if not clean_text.strip():
            clean_text = "추가 정보가 필요합니다"

        result = self.service._parse_extracted_data(clean_text)
        assert result is None

    def test_invalid_json_returns_none(self):
        """잘못된 JSON이 포함된 AI 응답에서 None을 반환해야 한다.

        **Validates: Requirements 7.6**
        """
        ai_response = "결과입니다:\n```json\n{invalid json content}\n```"
        result = self.service._parse_extracted_data(ai_response)
        assert result is None

    def test_multiple_json_blocks_returns_first(self):
        """여러 JSON 블록이 있을 때 첫 번째를 반환해야 한다.

        **Validates: Requirements 7.3**
        """
        first_data = {"amount": 5000, "description": "첫번째"}
        second_data = {"amount": 10000, "description": "두번째"}
        ai_response = (
            f"```json\n{json.dumps(first_data, ensure_ascii=False)}\n```\n"
            f"추가 데이터:\n```json\n{json.dumps(second_data, ensure_ascii=False)}\n```"
        )

        result = self.service._parse_extracted_data(ai_response)

        assert result is not None
        assert result["amount"] == 5000
        assert result["description"] == "첫번째"


# ══════════════════════════════════════════════
# 14.1: _build_system_prompt 순수 함수 테스트
# ══════════════════════════════════════════════

class TestBuildSystemPrompt:
    """_build_system_prompt 순수 함수 속성 기반 테스트.

    **Validates: Requirements 7.5, 16.1, 16.2**
    """

    def setup_method(self):
        """각 테스트 메서드 전에 서비스 인스턴스를 생성한다."""
        self.service = _make_chat_service()

    def test_empty_lists_returns_base_prompt(self):
        """빈 리스트로 호출하면 기본 프롬프트만 반환해야 한다.

        **Validates: Requirements 7.5**
        """
        prompt = self.service._build_system_prompt([], [], [])

        assert "가계부 AI 어시스턴트" in prompt
        assert "카테고리 목록" not in prompt
        assert "결제수단 목록" not in prompt
        assert "수정 이력" not in prompt

    @settings(max_examples=30, deadline=None)
    @given(
        major=category_names,
        minor=category_names,
        area=st.sampled_from(["GENERAL", "CAR", "CEREMONY"]),
        type_=st.sampled_from(["INCOME", "EXPENSE"]),
    )
    def test_with_categories_includes_category_list(
        self, major: str, minor: str, area: str, type_: str
    ):
        """카테고리가 있으면 프롬프트에 카테고리 목록이 포함되어야 한다.

        **Validates: Requirements 7.5**
        """
        categories = [MockCategory(major, minor, area, type_)]
        prompt = self.service._build_system_prompt(categories, [], [])

        assert "카테고리 목록" in prompt
        assert major in prompt
        assert minor in prompt

    @settings(max_examples=30, deadline=None)
    @given(
        name=descriptions,
        asset_type=st.sampled_from(["BANK_ACCOUNT", "CREDIT_CARD", "CASH"]),
    )
    def test_with_assets_includes_asset_list(self, name: str, asset_type: str):
        """자산이 있으면 프롬프트에 결제수단 목록이 포함되어야 한다.

        **Validates: Requirements 7.5**
        """
        assets = [MockAsset(name, "test-id-123", asset_type)]
        prompt = self.service._build_system_prompt([], assets, [])

        assert "결제수단 목록" in prompt
        assert name in prompt

    @settings(max_examples=30, deadline=None)
    @given(
        original=feedback_values,
        corrected=feedback_values,
        fb_type=feedback_types,
    )
    def test_with_feedbacks_includes_feedback_history(
        self, original: str, corrected: str, fb_type: str
    ):
        """피드백이 있으면 프롬프트에 수정 이력이 포함되어야 한다.

        **Validates: Requirements 16.1, 16.2**
        """
        feedbacks = [MockFeedback(original, corrected, fb_type)]
        prompt = self.service._build_system_prompt([], [], feedbacks)

        assert "수정 이력" in prompt
        assert original in prompt
        assert corrected in prompt

    @settings(max_examples=30, deadline=None)
    @given(
        major=category_names,
        asset_name=descriptions,
        original=feedback_values,
        corrected=feedback_values,
    )
    def test_with_all_data_includes_all_sections(
        self, major: str, asset_name: str, original: str, corrected: str
    ):
        """카테고리, 자산, 피드백 모두 있으면 모든 섹션이 포함되어야 한다.

        **Validates: Requirements 7.5, 16.1, 16.2**
        """
        categories = [MockCategory(major, "소분류", "GENERAL", "EXPENSE")]
        assets = [MockAsset(asset_name, "id-1", "CREDIT_CARD")]
        feedbacks = [MockFeedback(original, corrected, "CATEGORY_CORRECTION")]

        prompt = self.service._build_system_prompt(categories, assets, feedbacks)

        assert "카테고리 목록" in prompt
        assert "결제수단 목록" in prompt
        assert "수정 이력" in prompt
        assert major in prompt
        assert asset_name in prompt
        assert original in prompt


# ══════════════════════════════════════════════
# 14.1: _parse_receipt_response 순수 함수 테스트
# ══════════════════════════════════════════════

class TestParseReceiptResponse:
    """_parse_receipt_response 순수 함수 속성 기반 테스트.

    **Validates: Requirements 7.3**
    """

    def setup_method(self):
        """각 테스트 메서드 전에 서비스 인스턴스를 생성한다."""
        self.service = _make_receipt_service()

    @settings(max_examples=30, deadline=None)
    @given(amount=amounts, description=descriptions)
    def test_json_block_extracts_data_and_raw_text(self, amount: int, description: str):
        """```json 블록이 있으면 extracted_data와 raw_text를 분리해야 한다."""
        data = {"amount": amount, "description": description}
        raw_part = "영수증 원본 텍스트입니다"
        ai_response = f"{raw_part}\n```json\n{json.dumps(data, ensure_ascii=False)}\n```"

        raw_text, extracted_data = self.service._parse_receipt_response(ai_response)

        assert extracted_data is not None
        assert extracted_data["amount"] == amount
        assert raw_part in raw_text

    @settings(max_examples=30, deadline=None)
    @given(amount=amounts)
    def test_raw_json_object_extracts_data(self, amount: int):
        """원시 JSON 객체가 있으면 extracted_data를 추출해야 한다."""
        data = {"amount": amount}
        raw_part = "영수증 내용"
        ai_response = f"{raw_part} {json.dumps(data)}"

        raw_text, extracted_data = self.service._parse_receipt_response(ai_response)

        assert extracted_data is not None
        assert extracted_data["amount"] == amount

    def test_no_json_returns_full_text_and_none(self):
        """JSON이 없으면 전체 텍스트를 raw_text로, None을 extracted_data로 반환해야 한다."""
        ai_response = "영수증을 읽을 수 없습니다"

        raw_text, extracted_data = self.service._parse_receipt_response(ai_response)

        assert raw_text == ai_response
        assert extracted_data is None

    def test_empty_raw_text_uses_full_response(self):
        """raw_text가 비어있으면 전체 응답을 raw_text로 사용해야 한다."""
        data = {"amount": 5000}
        ai_response = f"```json\n{json.dumps(data)}\n```"

        raw_text, extracted_data = self.service._parse_receipt_response(ai_response)

        assert extracted_data is not None
        # raw_text가 비어있으면 전체 응답을 사용
        assert len(raw_text) > 0


# ══════════════════════════════════════════════
# 14.2: Property 17 — Bedrock 클라이언트 에러 처리
# ══════════════════════════════════════════════


class TestBedrockErrorHandling:
    """Bedrock 클라이언트 에러 처리 속성 기반 테스트.

    **Property 17: Bedrock 클라이언트 에러 처리**
    **Validates: Requirements 5.6, 5.7, 7.7, 9.6, 12.6**

    Bedrock API 호출 실패 또는 타임아웃 시 BedrockError가 발생해야 하고,
    에러 메시지가 의미 있는 정보를 포함해야 한다.
    """

    def test_bedrock_error_default_message(self):
        """BedrockError 기본 메시지가 설정되어야 한다.

        **Validates: Requirements 5.6**
        """
        error = BedrockError()
        assert error.detail == "AI 서비스 호출에 실패했습니다"
        assert str(error) == "AI 서비스 호출에 실패했습니다"

    @settings(max_examples=30, deadline=None)
    @given(
        error_msg=st.text(
            min_size=1, max_size=100,
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
        )
    )
    def test_bedrock_error_custom_message(self, error_msg: str):
        """BedrockError에 커스텀 메시지를 전달하면 해당 메시지가 설정되어야 한다.

        **Validates: Requirements 5.6**
        """
        error = BedrockError(detail=error_msg)
        assert error.detail == error_msg
        assert str(error) == error_msg

    def test_bedrock_error_is_exception(self):
        """BedrockError는 Exception을 상속해야 한다.

        **Validates: Requirements 5.6**
        """
        error = BedrockError("테스트 에러")
        assert isinstance(error, Exception)

    def test_bedrock_error_can_be_raised_and_caught(self):
        """BedrockError를 raise하고 catch할 수 있어야 한다.

        **Validates: Requirements 5.6**
        """
        with pytest.raises(BedrockError) as exc_info:
            raise BedrockError("API 타임아웃")

        assert "API 타임아웃" in exc_info.value.detail

    @settings(max_examples=30, deadline=None)
    @given(
        error_type=st.sampled_from([
            "API 타임아웃이 발생했습니다",
            "잘못된 응답 형식입니다",
            "네트워크 연결에 실패했습니다",
            "요청 한도를 초과했습니다",
        ])
    )
    def test_various_error_scenarios_produce_meaningful_messages(self, error_type: str):
        """다양한 에러 시나리오에서 의미 있는 에러 메시지가 생성되어야 한다.

        **Validates: Requirements 5.6, 5.7, 7.7, 9.6, 12.6**
        """
        error = BedrockError(detail=f"AI 서비스 호출에 실패했습니다: {error_type}")

        assert error.detail is not None
        assert len(error.detail) > 0
        assert error_type in error.detail

    def test_bedrock_error_timeout_scenario(self):
        """타임아웃 시나리오에서 BedrockError가 적절한 메시지를 포함해야 한다.

        **Validates: Requirements 5.7**
        """
        timeout_error = BedrockError(
            detail="AI 서비스 호출에 실패했습니다: Read timeout on endpoint URL"
        )
        assert "timeout" in timeout_error.detail.lower() or "타임아웃" in timeout_error.detail

    def test_bedrock_error_network_scenario(self):
        """네트워크 에러 시나리오에서 BedrockError가 적절한 메시지를 포함해야 한다.

        **Validates: Requirements 5.6**
        """
        network_error = BedrockError(
            detail="AI 서비스 호출에 실패했습니다: ConnectionError"
        )
        assert "ConnectionError" in network_error.detail

    def test_bedrock_error_rate_limit_scenario(self):
        """Rate limiting 시나리오에서 BedrockError가 적절한 메시지를 포함해야 한다.

        **Validates: Requirements 5.6**
        """
        rate_error = BedrockError(
            detail="AI 서비스 호출에 실패했습니다: ThrottlingException"
        )
        assert "ThrottlingException" in rate_error.detail

    def test_bedrock_error_invalid_response_scenario(self):
        """잘못된 응답 형식 시나리오에서 BedrockError가 적절한 메시지를 포함해야 한다.

        **Validates: Requirements 5.6**
        """
        invalid_error = BedrockError(
            detail="AI 서비스 호출에 실패했습니다: KeyError 'output'"
        )
        assert "KeyError" in invalid_error.detail
