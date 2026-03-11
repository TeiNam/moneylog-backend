"""
AIChatService 단위 테스트 및 속성 기반 테스트.

세션 CRUD, 메시지 전송, 거래 확정, 접근 권한, 에러 케이스를 검증한다.
BedrockClient는 MockBedrockClient로 모킹하여 외부 의존성을 제거한다.
"""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.models.enums import MessageRole, TransactionSource
from app.repositories.ai_feedback_repository import AIFeedbackRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.services.ai_chat_service import AIChatService
from tests.conftest import create_test_user


# ══════════════════════════════════════════════
# Mock 클래스
# ══════════════════════════════════════════════


class MockBedrockClient:
    """테스트용 Bedrock 클라이언트 모킹."""

    def __init__(self, response: str = "") -> None:
        self.response = response
        self.call_count = 0

    async def converse(
        self, system_prompt: str, messages: list[dict], max_tokens: int = 4096
    ) -> str:
        self.call_count += 1
        return self.response

    async def converse_with_image(
        self,
        system_prompt: str,
        image_bytes: bytes,
        content_type: str,
        user_message: str = "",
        max_tokens: int = 4096,
    ) -> str:
        self.call_count += 1
        return self.response


class MockTransactionService:
    """테스트용 TransactionService 모킹."""

    def __init__(self) -> None:
        self.created_transactions = []
        self.call_count = 0

    async def create(self, user, data):
        """거래 생성을 모킹한다. 간단한 객체를 반환."""
        self.call_count += 1

        class MockTransaction:
            def __init__(self, tx_id, source):
                self.id = tx_id
                self.source = source
                self.date = data.date
                self.amount = data.amount
                self.description = data.description

        tx = MockTransaction(uuid.uuid4(), data.source.value)
        self.created_transactions.append(tx)
        return tx


# ══════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════


def _build_service(
    db_session,
    bedrock_response: str = "",
    transaction_service=None,
) -> tuple[AIChatService, MockBedrockClient, MockTransactionService]:
    """테스트용 AIChatService 인스턴스를 생성한다."""
    session_repo = ChatSessionRepository(db_session)
    message_repo = ChatMessageRepository(db_session)
    feedback_repo = AIFeedbackRepository(db_session)
    category_repo = CategoryRepository(db_session)
    asset_repo = AssetRepository(db_session)
    mock_bedrock = MockBedrockClient(response=bedrock_response)
    mock_tx_service = transaction_service or MockTransactionService()

    service = AIChatService(
        session_repo=session_repo,
        message_repo=message_repo,
        feedback_repo=feedback_repo,
        bedrock_client=mock_bedrock,
        transaction_service=mock_tx_service,
        category_repo=category_repo,
        asset_repo=asset_repo,
    )
    return service, mock_bedrock, mock_tx_service


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_session(db_session):
    """세션 생성 정상 동작 검증."""
    user = await create_test_user(db_session)
    service, _, _ = _build_service(db_session)

    session = await service.create_session(user, title="테스트 세션")

    assert session.user_id == user.id
    assert session.title == "테스트 세션"
    assert session.created_at is not None


@pytest.mark.asyncio
async def test_get_sessions(db_session):
    """세션 목록 조회 검증."""
    user = await create_test_user(db_session)
    service, _, _ = _build_service(db_session)

    await service.create_session(user, title="세션1")
    await service.create_session(user, title="세션2")

    sessions = await service.get_sessions(user)
    assert len(sessions) == 2


@pytest.mark.asyncio
async def test_get_session_detail(db_session):
    """세션 상세 조회 검증."""
    user = await create_test_user(db_session)
    service, _, _ = _build_service(db_session)

    session = await service.create_session(user, title="상세 조회 테스트")
    detail = await service.get_session_detail(user, session.id)

    assert detail["session"].id == session.id
    assert isinstance(detail["messages"], list)


@pytest.mark.asyncio
async def test_delete_session(db_session):
    """세션 삭제 정상 동작 검증."""
    user = await create_test_user(db_session)
    service, _, _ = _build_service(db_session)

    session = await service.create_session(user, title="삭제 테스트")
    await service.delete_session(user, session.id)

    with pytest.raises(NotFoundError):
        await service.get_session_detail(user, session.id)


@pytest.mark.asyncio
async def test_forbidden_error_on_other_user_session(db_session):
    """다른 사용자 세션 접근 시 ForbiddenError 검증."""
    user_a = await create_test_user(db_session, email="a@test.com", nickname="A")
    user_b = await create_test_user(db_session, email="b@test.com", nickname="B")
    service, _, _ = _build_service(db_session)

    session = await service.create_session(user_a, title="A의 세션")

    with pytest.raises(ForbiddenError):
        await service.get_session_detail(user_b, session.id)

    with pytest.raises(ForbiddenError):
        await service.delete_session(user_b, session.id)


@pytest.mark.asyncio
async def test_not_found_error_on_nonexistent_session(db_session):
    """존재하지 않는 세션 접근 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    service, _, _ = _build_service(db_session)

    fake_id = uuid.uuid4()

    with pytest.raises(NotFoundError):
        await service.get_session_detail(user, fake_id)

    with pytest.raises(NotFoundError):
        await service.delete_session(user, fake_id)


@pytest.mark.asyncio
async def test_send_message_and_ai_response(db_session):
    """메시지 전송 및 AI 응답 저장 검증 (BedrockClient 모킹)."""
    user = await create_test_user(db_session)
    ai_response = '오늘 점심으로 김치찌개를 드셨군요!\n\n```json\n{"date": "2025-06-15", "type": "EXPENSE", "major_category": "식비", "amount": 9000, "description": "김치찌개"}\n```'
    service, mock_bedrock, _ = _build_service(db_session, bedrock_response=ai_response)

    session = await service.create_session(user)
    ai_msg = await service.send_message(user, session.id, "오늘 점심 김치찌개 9000원")

    assert ai_msg.role == MessageRole.ASSISTANT.value
    assert ai_msg.content == ai_response
    assert ai_msg.extracted_data is not None
    assert ai_msg.extracted_data["amount"] == 9000
    assert mock_bedrock.call_count == 1


@pytest.mark.asyncio
async def test_confirm_transaction_normal(db_session):
    """거래 확정 정상 동작 및 source=AI_CHAT 검증."""
    user = await create_test_user(db_session)
    ai_response = '```json\n{"date": "2025-06-15", "type": "EXPENSE", "area": "GENERAL", "major_category": "식비", "amount": 9000, "discount": 0, "description": "김치찌개"}\n```'
    mock_tx_service = MockTransactionService()
    service, _, _ = _build_service(
        db_session, bedrock_response=ai_response, transaction_service=mock_tx_service
    )

    session = await service.create_session(user)
    ai_msg = await service.send_message(user, session.id, "점심 김치찌개 9000원")

    transaction = await service.confirm_transaction(user, ai_msg.id)

    assert transaction is not None
    assert transaction.source == TransactionSource.AI_CHAT.value
    assert mock_tx_service.call_count == 1


@pytest.mark.asyncio
async def test_confirm_transaction_bad_request_no_extracted_data(db_session):
    """extracted_data 없는 메시지 확정 시 BadRequestError 검증."""
    user = await create_test_user(db_session)
    # JSON이 없는 AI 응답
    ai_response = "안녕하세요! 무엇을 도와드릴까요?"
    service, _, _ = _build_service(db_session, bedrock_response=ai_response)

    session = await service.create_session(user)
    ai_msg = await service.send_message(user, session.id, "안녕")

    with pytest.raises(BadRequestError):
        await service.confirm_transaction(user, ai_msg.id)


@pytest.mark.asyncio
async def test_confirm_transaction_conflict_already_confirmed(db_session):
    """이미 확정된 메시지 재확정 시 ConflictError 검증."""
    user = await create_test_user(db_session)
    ai_response = '```json\n{"date": "2025-06-15", "type": "EXPENSE", "area": "GENERAL", "major_category": "식비", "amount": 9000, "discount": 0, "description": "김치찌개"}\n```'
    service, _, _ = _build_service(db_session, bedrock_response=ai_response)

    session = await service.create_session(user)
    ai_msg = await service.send_message(user, session.id, "점심 김치찌개 9000원")

    # 첫 번째 확정
    await service.confirm_transaction(user, ai_msg.id)

    # 두 번째 확정 시도 → ConflictError
    with pytest.raises(ConflictError):
        await service.confirm_transaction(user, ai_msg.id)


@pytest.mark.asyncio
async def test_bedrock_error_handling(db_session):
    """Bedrock API 실패 시 에러 처리 검증."""
    from app.services.bedrock_client import BedrockError

    user = await create_test_user(db_session)
    service, mock_bedrock, _ = _build_service(db_session)

    # BedrockClient가 에러를 발생시키도록 설정
    async def raise_error(*args, **kwargs):
        raise BedrockError("AI 서비스 호출에 실패했습니다")

    mock_bedrock.converse = raise_error

    session = await service.create_session(user)

    with pytest.raises(BedrockError):
        await service.send_message(user, session.id, "테스트 메시지")


# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════

# Hypothesis 전략 정의
session_titles = st.one_of(
    st.none(),
    st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    ),
)


# ──────────────────────────────────────────────
# Property 1: 채팅 세션 CRUD 라운드트립
# Feature: moneylog-backend-phase7, Property 1: 채팅 세션 CRUD 라운드트립
# Validates: Requirements 6.1, 6.2, 6.3, 6.5, 6.7
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(title=session_titles)
async def test_property_session_crud_roundtrip(db_session, title):
    """유효한 제목으로 세션 생성 후 필드 일치, 목록 포함, 삭제 후 NotFoundError를 검증한다.

    **Validates: Requirements 6.1, 6.2, 6.3, 6.5, 6.7**
    """
    user = await create_test_user(
        db_session,
        email=f"p1_{uuid.uuid4().hex[:8]}@test.com",
        nickname="P1",
    )
    service, _, _ = _build_service(db_session)

    # 생성
    session = await service.create_session(user, title=title)
    assert session.user_id == user.id
    assert session.title == title
    assert session.created_at is not None

    # 목록에 포함
    sessions = await service.get_sessions(user)
    session_ids = [s.id for s in sessions]
    assert session.id in session_ids

    # 삭제 후 NotFoundError
    await service.delete_session(user, session.id)
    with pytest.raises(NotFoundError):
        await service.get_session_detail(user, session.id)


# ──────────────────────────────────────────────
# Property 2: 채팅 세션 접근 권한
# Feature: moneylog-backend-phase7, Property 2: 채팅 세션 접근 권한
# Validates: Requirements 6.6
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(title=session_titles)
async def test_property_session_access_control(db_session, title):
    """사용자 A가 생성한 세션을 사용자 B가 접근하면 ForbiddenError가 발생해야 한다.

    **Validates: Requirements 6.6**
    """
    uid = uuid.uuid4().hex[:6]
    user_a = await create_test_user(
        db_session, email=f"p2a_{uid}@test.com", nickname="P2A"
    )
    user_b = await create_test_user(
        db_session, email=f"p2b_{uid}@test.com", nickname="P2B"
    )
    service, _, _ = _build_service(db_session)

    session = await service.create_session(user_a, title=title)

    # B가 A의 세션 상세 조회 → ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.get_session_detail(user_b, session.id)

    # B가 A의 세션 삭제 → ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.delete_session(user_b, session.id)


# ──────────────────────────────────────────────
# Property 4: AI 추출 데이터 파싱
# Feature: moneylog-backend-phase7, Property 4: AI 추출 데이터 파싱
# Validates: Requirements 7.3, 7.6
# ──────────────────────────────────────────────

# JSON 데이터 생성 전략
json_amounts = st.integers(min_value=100, max_value=10_000_000)
json_descriptions = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(amount=json_amounts, description=json_descriptions)
async def test_property_parse_extracted_data(db_session, amount, description):
    """다양한 JSON 형식의 AI 응답에서 _parse_extracted_data가 dict 또는 None을 반환해야 한다.

    **Validates: Requirements 7.3, 7.6**
    """
    service, _, _ = _build_service(db_session)

    # ```json 블록 형태
    json_data = {"amount": amount, "description": description}
    response_with_json = f"거래를 분석했습니다.\n\n```json\n{json.dumps(json_data, ensure_ascii=False)}\n```"
    result = service._parse_extracted_data(response_with_json)
    assert isinstance(result, dict)
    assert result["amount"] == amount

    # JSON이 없는 응답
    response_without_json = "추가 정보가 필요합니다. 금액을 알려주세요."
    result_none = service._parse_extracted_data(response_without_json)
    assert result_none is None


# ──────────────────────────────────────────────
# Property 5: 거래 확정 라운드트립 (AI 채팅)
# Feature: moneylog-backend-phase7, Property 5: 거래 확정 라운드트립 (AI 채팅)
# Validates: Requirements 8.1, 8.2, 8.3, 8.4
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(amount=st.integers(min_value=100, max_value=1_000_000))
async def test_property_confirm_transaction_roundtrip(db_session, amount):
    """extracted_data가 있는 AI 메시지에 대해 confirm_transaction 호출 시 Transaction이 생성되고 source가 AI_CHAT이어야 한다.

    **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    """
    user = await create_test_user(
        db_session,
        email=f"p5_{uuid.uuid4().hex[:8]}@test.com",
        nickname="P5",
    )
    json_data = {
        "date": "2025-06-15",
        "type": "EXPENSE",
        "area": "GENERAL",
        "major_category": "식비",
        "amount": amount,
        "discount": 0,
        "description": "테스트 거래",
    }
    ai_response = f"```json\n{json.dumps(json_data, ensure_ascii=False)}\n```"
    mock_tx_service = MockTransactionService()
    service, _, _ = _build_service(
        db_session, bedrock_response=ai_response, transaction_service=mock_tx_service
    )

    session = await service.create_session(user)
    ai_msg = await service.send_message(user, session.id, f"테스트 {amount}원")

    transaction = await service.confirm_transaction(user, ai_msg.id)

    assert transaction is not None
    assert transaction.source == TransactionSource.AI_CHAT.value
    assert mock_tx_service.call_count == 1


# ──────────────────────────────────────────────
# Property 6: 거래 확정 중복 방지
# Feature: moneylog-backend-phase7, Property 6: 거래 확정 중복 방지
# Validates: Requirements 8.6, 10.6
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(amount=st.integers(min_value=100, max_value=1_000_000))
async def test_property_duplicate_confirm_prevention(db_session, amount):
    """이미 확정된 메시지를 재확정하면 ConflictError가 발생해야 한다.

    **Validates: Requirements 8.6, 10.6**
    """
    user = await create_test_user(
        db_session,
        email=f"p6_{uuid.uuid4().hex[:8]}@test.com",
        nickname="P6",
    )
    json_data = {
        "date": "2025-06-15",
        "type": "EXPENSE",
        "area": "GENERAL",
        "major_category": "식비",
        "amount": amount,
        "discount": 0,
        "description": "중복 테스트",
    }
    ai_response = f"```json\n{json.dumps(json_data, ensure_ascii=False)}\n```"
    service, _, _ = _build_service(db_session, bedrock_response=ai_response)

    session = await service.create_session(user)
    ai_msg = await service.send_message(user, session.id, f"테스트 {amount}원")

    # 첫 번째 확정 성공
    await service.confirm_transaction(user, ai_msg.id)

    # 두 번째 확정 → ConflictError
    with pytest.raises(ConflictError):
        await service.confirm_transaction(user, ai_msg.id)


# ──────────────────────────────────────────────
# Property 7: 거래 확정 전제 조건
# Feature: moneylog-backend-phase7, Property 7: 거래 확정 전제 조건
# Validates: Requirements 8.5, 10.5
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(content=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N"))))
async def test_property_confirm_preconditions(db_session, content):
    """extracted_data가 없는 메시지에 대해 확정 시도 시 BadRequestError가 발생해야 한다.

    **Validates: Requirements 8.5, 10.5**
    """
    user = await create_test_user(
        db_session,
        email=f"p7_{uuid.uuid4().hex[:8]}@test.com",
        nickname="P7",
    )
    # JSON이 없는 AI 응답
    ai_response = "추가 정보가 필요합니다. 금액을 알려주세요."
    service, _, _ = _build_service(db_session, bedrock_response=ai_response)

    session = await service.create_session(user)
    ai_msg = await service.send_message(user, session.id, content)

    # extracted_data가 없으므로 BadRequestError
    with pytest.raises(BadRequestError):
        await service.confirm_transaction(user, ai_msg.id)
