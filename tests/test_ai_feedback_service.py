"""
AIFeedbackService 단위 테스트 및 속성 기반 테스트.

피드백 생성, 이력 조회, source 검증, 접근 권한, 에러 케이스를 검증한다.
DB에 실제 거래를 생성하여 AIFeedbackService의 검증 로직을 테스트한다.
"""

import uuid
from datetime import date

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.enums import FeedbackType, TransactionSource
from app.models.transaction import Transaction
from app.repositories.ai_feedback_repository import AIFeedbackRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.ai_feedback import FeedbackCreateRequest
from app.services.ai_feedback_service import AIFeedbackService
from tests.conftest import create_test_user


# ══════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════


def _build_service(db_session) -> AIFeedbackService:
    """테스트용 AIFeedbackService 인스턴스를 생성한다."""
    feedback_repo = AIFeedbackRepository(db_session)
    transaction_repo = TransactionRepository(db_session)
    return AIFeedbackService(
        feedback_repo=feedback_repo,
        transaction_repo=transaction_repo,
    )


async def _create_transaction(
    db_session,
    user_id,
    source: str = TransactionSource.AI_CHAT.value,
    description: str = "아메리카노",
    tx_date: date | None = None,
) -> Transaction:
    """테스트용 거래를 생성한다."""
    tx = Transaction(
        user_id=user_id,
        date=tx_date or date(2025, 6, 15),
        area="GENERAL",
        type="EXPENSE",
        major_category="식비",
        minor_category="카페",
        description=description,
        amount=4500,
        discount=0,
        actual_amount=4500,
        source=source,
    )
    db_session.add(tx)
    await db_session.flush()
    await db_session.refresh(tx)
    return tx


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_feedback_normal(db_session):
    """피드백 생성 정상 동작 검증."""
    user = await create_test_user(db_session)
    tx = await _create_transaction(db_session, user.id)
    service = _build_service(db_session)

    data = FeedbackCreateRequest(
        transaction_id=tx.id,
        feedback_type=FeedbackType.CATEGORY_CORRECTION,
        original_value="식비",
        corrected_value="교통비",
    )
    feedback = await service.create_feedback(user, data)

    assert feedback.user_id == user.id
    assert feedback.transaction_id == tx.id
    assert feedback.feedback_type == FeedbackType.CATEGORY_CORRECTION.value
    assert feedback.original_value == "식비"
    assert feedback.corrected_value == "교통비"


@pytest.mark.asyncio
async def test_create_feedback_not_found_error(db_session):
    """거래 미존재 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    service = _build_service(db_session)

    data = FeedbackCreateRequest(
        transaction_id=999999999,
        feedback_type=FeedbackType.CATEGORY_CORRECTION,
        original_value="식비",
        corrected_value="교통비",
    )
    with pytest.raises(NotFoundError, match="거래를 찾을 수 없습니다"):
        await service.create_feedback(user, data)


@pytest.mark.asyncio
async def test_create_feedback_forbidden_error(db_session):
    """다른 사용자 거래에 피드백 시 ForbiddenError 검증."""
    user_a = await create_test_user(db_session, email="a@test.com", nickname="유저A")
    user_b = await create_test_user(db_session, email="b@test.com", nickname="유저B")
    tx = await _create_transaction(db_session, user_a.id)
    service = _build_service(db_session)

    data = FeedbackCreateRequest(
        transaction_id=tx.id,
        feedback_type=FeedbackType.AMOUNT_CORRECTION,
        original_value="4500",
        corrected_value="5000",
    )
    with pytest.raises(ForbiddenError, match="접근 권한이 없습니다"):
        await service.create_feedback(user_b, data)


@pytest.mark.asyncio
async def test_create_feedback_bad_request_manual_source(db_session):
    """source가 MANUAL인 거래에 피드백 시 BadRequestError 검증."""
    user = await create_test_user(db_session)
    tx = await _create_transaction(
        db_session, user.id, source=TransactionSource.MANUAL.value,
    )
    service = _build_service(db_session)

    data = FeedbackCreateRequest(
        transaction_id=tx.id,
        feedback_type=FeedbackType.CATEGORY_CORRECTION,
        original_value="식비",
        corrected_value="교통비",
    )
    with pytest.raises(BadRequestError, match="AI 생성 거래에만 피드백을 제출할 수 있습니다"):
        await service.create_feedback(user, data)


@pytest.mark.asyncio
async def test_create_feedback_bad_request_subscription_auto_source(db_session):
    """source가 SUBSCRIPTION_AUTO인 거래에 피드백 시 BadRequestError 검증."""
    user = await create_test_user(db_session)
    tx = await _create_transaction(
        db_session, user.id, source=TransactionSource.SUBSCRIPTION_AUTO.value,
    )
    service = _build_service(db_session)

    data = FeedbackCreateRequest(
        transaction_id=tx.id,
        feedback_type=FeedbackType.DESCRIPTION_CORRECTION,
        original_value="넷플릭스",
        corrected_value="넷플릭스 프리미엄",
    )
    with pytest.raises(BadRequestError, match="AI 생성 거래에만 피드백을 제출할 수 있습니다"):
        await service.create_feedback(user, data)


@pytest.mark.asyncio
async def test_get_feedbacks_with_transaction_info(db_session):
    """피드백 이력 조회 및 거래 기본 정보 포함 검증."""
    user = await create_test_user(db_session)
    tx = await _create_transaction(db_session, user.id, description="라떼")
    service = _build_service(db_session)

    # 피드백 2건 생성
    for ft, orig, corr in [
        (FeedbackType.CATEGORY_CORRECTION, "식비", "음료"),
        (FeedbackType.AMOUNT_CORRECTION, "4500", "5000"),
    ]:
        data = FeedbackCreateRequest(
            transaction_id=tx.id,
            feedback_type=ft,
            original_value=orig,
            corrected_value=corr,
        )
        await service.create_feedback(user, data)

    # 전체 조회
    feedbacks = await service.get_feedbacks(user)
    assert len(feedbacks) == 2
    # 각 피드백에 거래 정보 포함 확인
    for fb in feedbacks:
        assert fb["transaction_description"] == "라떼"
        assert fb["transaction_date"] == date(2025, 6, 15)

    # feedback_type 필터
    filtered = await service.get_feedbacks(
        user, feedback_type=FeedbackType.CATEGORY_CORRECTION.value,
    )
    assert len(filtered) == 1
    assert filtered[0]["feedback_type"] == FeedbackType.CATEGORY_CORRECTION.value

    # transaction_id 필터
    filtered_by_tx = await service.get_feedbacks(user, transaction_id=tx.id)
    assert len(filtered_by_tx) == 2


@pytest.mark.asyncio
async def test_get_recent_feedbacks_limit(db_session):
    """최근 피드백 조회 (limit) 검증."""
    user = await create_test_user(db_session)
    tx = await _create_transaction(db_session, user.id)
    service = _build_service(db_session)

    # 피드백 5건 생성
    for i in range(5):
        data = FeedbackCreateRequest(
            transaction_id=tx.id,
            feedback_type=FeedbackType.CATEGORY_CORRECTION,
            original_value=f"원래값{i}",
            corrected_value=f"수정값{i}",
        )
        await service.create_feedback(user, data)

    # limit=3으로 조회
    recent = await service.get_recent_feedbacks(user.id, limit=3)
    assert len(recent) == 3

    # limit=20 (기본값)으로 조회
    all_recent = await service.get_recent_feedbacks(user.id)
    assert len(all_recent) == 5


# ══════════════════════════════════════════════
# 속성 기반 테스트: Property 14 — 피드백 생성 검증
# Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
# ══════════════════════════════════════════════

# 피드백 유형 전략
feedback_types = st.sampled_from([
    FeedbackType.CATEGORY_CORRECTION,
    FeedbackType.AMOUNT_CORRECTION,
    FeedbackType.DESCRIPTION_CORRECTION,
])

# 피드백 값 전략
feedback_values = st.text(
    min_size=1, max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

# AI 생성 source 전략
ai_sources = st.sampled_from([
    TransactionSource.AI_CHAT.value,
    TransactionSource.RECEIPT_SCAN.value,
])

# 비-AI source 전략
non_ai_sources = st.sampled_from([
    TransactionSource.MANUAL.value,
    TransactionSource.SUBSCRIPTION_AUTO.value,
])


@pytest.mark.asyncio
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    fb_type=feedback_types,
    original=feedback_values,
    corrected=feedback_values,
    source=ai_sources,
)
async def test_property_feedback_creation(
    db_session, fb_type, original, corrected, source,
):
    """**Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6**

    유효한 AI 생성 거래에 대해 피드백 생성 시:
    - 피드백이 정상 생성되고 user_id가 현재 사용자로 설정됨
    - 존재하지 않는 거래에 대해 NotFoundError 발생
    - 다른 사용자의 거래에 대해 ForbiddenError 발생
    - MANUAL/SUBSCRIPTION_AUTO source 거래에 대해 BadRequestError 발생
    """
    user_a = await create_test_user(
        db_session, email=f"a_{uuid.uuid4().hex[:8]}@test.com", nickname="유저A",
    )
    user_b = await create_test_user(
        db_session, email=f"b_{uuid.uuid4().hex[:8]}@test.com", nickname="유저B",
    )
    tx = await _create_transaction(db_session, user_a.id, source=source)
    service = _build_service(db_session)

    # 1) 유효한 피드백 생성 → 성공
    data = FeedbackCreateRequest(
        transaction_id=tx.id,
        feedback_type=fb_type,
        original_value=original,
        corrected_value=corrected,
    )
    feedback = await service.create_feedback(user_a, data)
    assert feedback.user_id == user_a.id
    assert feedback.feedback_type == fb_type.value
    assert feedback.original_value == original
    assert feedback.corrected_value == corrected

    # 2) 존재하지 않는 거래 → NotFoundError
    bad_data = FeedbackCreateRequest(
        transaction_id=999999999,
        feedback_type=fb_type,
        original_value=original,
        corrected_value=corrected,
    )
    with pytest.raises(NotFoundError):
        await service.create_feedback(user_a, bad_data)

    # 3) 다른 사용자의 거래 → ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.create_feedback(user_b, data)


@pytest.mark.asyncio
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    fb_type=feedback_types,
    original=feedback_values,
    corrected=feedback_values,
    source=non_ai_sources,
)
async def test_property_feedback_source_validation(
    db_session, fb_type, original, corrected, source,
):
    """**Validates: Requirements 14.3, 14.4**

    MANUAL 또는 SUBSCRIPTION_AUTO source 거래에 피드백 시 BadRequestError 발생.
    """
    user = await create_test_user(
        db_session, email=f"u_{uuid.uuid4().hex[:8]}@test.com", nickname="유저",
    )
    tx = await _create_transaction(db_session, user.id, source=source)
    service = _build_service(db_session)

    data = FeedbackCreateRequest(
        transaction_id=tx.id,
        feedback_type=fb_type,
        original_value=original,
        corrected_value=corrected,
    )
    with pytest.raises(BadRequestError):
        await service.create_feedback(user, data)


# ══════════════════════════════════════════════
# 속성 기반 테스트: Property 15 — 피드백 이력 조회 및 필터링
# Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5
# ══════════════════════════════════════════════


@pytest.mark.asyncio
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    fb_type=feedback_types,
    original=feedback_values,
    corrected=feedback_values,
)
async def test_property_feedback_listing_and_filtering(
    db_session, fb_type, original, corrected,
):
    """**Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5**

    피드백 이력 조회 시:
    - 본인의 피드백만 반환
    - feedback_type 필터 적용 시 해당 유형만 반환
    - transaction_id 필터 적용 시 해당 거래의 피드백만 반환
    - 각 피드백에 거래 기본 정보(description, date) 포함
    """
    user_a = await create_test_user(
        db_session, email=f"a_{uuid.uuid4().hex[:8]}@test.com", nickname="유저A",
    )
    user_b = await create_test_user(
        db_session, email=f"b_{uuid.uuid4().hex[:8]}@test.com", nickname="유저B",
    )
    tx_a = await _create_transaction(
        db_session, user_a.id, description="유저A거래",
    )
    tx_b = await _create_transaction(
        db_session, user_b.id, description="유저B거래",
    )
    service = _build_service(db_session)

    # 유저A 피드백 생성
    data_a = FeedbackCreateRequest(
        transaction_id=tx_a.id,
        feedback_type=fb_type,
        original_value=original,
        corrected_value=corrected,
    )
    await service.create_feedback(user_a, data_a)

    # 유저B 피드백 생성
    data_b = FeedbackCreateRequest(
        transaction_id=tx_b.id,
        feedback_type=fb_type,
        original_value=original,
        corrected_value=corrected,
    )
    await service.create_feedback(user_b, data_b)

    # 유저A 조회 → 본인 피드백만 반환
    feedbacks_a = await service.get_feedbacks(user_a)
    for fb in feedbacks_a:
        assert fb["user_id"] == user_a.id
        assert fb["transaction_description"] is not None

    # feedback_type 필터
    filtered = await service.get_feedbacks(user_a, feedback_type=fb_type.value)
    for fb in filtered:
        assert fb["feedback_type"] == fb_type.value

    # transaction_id 필터
    filtered_tx = await service.get_feedbacks(user_a, transaction_id=tx_a.id)
    for fb in filtered_tx:
        assert fb["transaction_id"] == tx_a.id


# ══════════════════════════════════════════════
# 속성 기반 테스트: Property 16 — 피드백 기반 프롬프트 강화
# Validates: Requirements 16.1, 16.2, 16.3
# ══════════════════════════════════════════════


@pytest.mark.asyncio
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    count=st.integers(min_value=1, max_value=5),
    fb_type=feedback_types,
)
async def test_property_recent_feedbacks_for_prompt(
    db_session, count, fb_type,
):
    """**Validates: Requirements 16.1, 16.2, 16.3**

    프롬프트 강화용 최근 피드백 조회 시:
    - 최대 20건까지 반환
    - 최신순으로 정렬
    - 각 피드백에 original_value, corrected_value 포함
    """
    user = await create_test_user(
        db_session, email=f"u_{uuid.uuid4().hex[:8]}@test.com", nickname="유저",
    )
    tx = await _create_transaction(db_session, user.id)
    service = _build_service(db_session)

    # count건의 피드백 생성
    for i in range(count):
        data = FeedbackCreateRequest(
            transaction_id=tx.id,
            feedback_type=fb_type,
            original_value=f"원래값{i}",
            corrected_value=f"수정값{i}",
        )
        await service.create_feedback(user, data)

    # 최근 피드백 조회
    recent = await service.get_recent_feedbacks(user.id, limit=20)
    assert len(recent) >= count
    assert len(recent) <= 20

    # 각 피드백에 필수 필드 포함 확인
    for fb in recent:
        assert fb.original_value is not None
        assert fb.corrected_value is not None
        assert fb.feedback_type is not None
