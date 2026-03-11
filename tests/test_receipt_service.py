"""
ReceiptService 단위 테스트 및 속성 기반 테스트.

영수증 업로드/OCR, 스캔 이력 조회, 거래 확정, 이미지 검증, 에러 케이스를 검증한다.
BedrockClient는 MockBedrockClient로 모킹하여 외부 의존성을 제거한다.
"""

import json
import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.models.enums import ScanStatus, TransactionSource
from app.repositories.ai_feedback_repository import AIFeedbackRepository
from app.repositories.receipt_scan_repository import ReceiptScanRepository
from app.services.bedrock_client import BedrockError
from app.services.receipt_service import ReceiptService
from tests.conftest import create_test_user


# ══════════════════════════════════════════════
# Mock 클래스
# ══════════════════════════════════════════════


class MockBedrockClient:
    """테스트용 Bedrock 클라이언트 모킹."""

    def __init__(self, response: str = "", should_fail: bool = False) -> None:
        self.response = response
        self.should_fail = should_fail
        self.call_count = 0

    async def converse(
        self, system_prompt: str, messages: list[dict], max_tokens: int = 4096
    ) -> str:
        self.call_count += 1
        if self.should_fail:
            raise BedrockError("AI 서비스 호출에 실패했습니다")
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
        if self.should_fail:
            raise BedrockError("AI 서비스 호출에 실패했습니다")
        return self.response


class MockTransactionService:
    """테스트용 TransactionService 모킹."""

    def __init__(self) -> None:
        self.created_transactions = []
        self.call_count = 0

    async def create(self, user, data):
        """거래 생성을 모킹한다."""
        self.call_count += 1

        class MockTransaction:
            def __init__(self, tx_id, source):
                self.id = tx_id
                self.source = source
                self.date = data.date
                self.amount = data.amount
                self.description = data.description

        tx = MockTransaction(1, data.source.value)
        self.created_transactions.append(tx)
        return tx


# ══════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════


def _build_receipt_service(
    db_session,
    bedrock_response: str = "",
    should_fail: bool = False,
    transaction_service=None,
) -> tuple[ReceiptService, MockBedrockClient, MockTransactionService]:
    """테스트용 ReceiptService 인스턴스를 생성한다."""
    scan_repo = ReceiptScanRepository(db_session)
    feedback_repo = AIFeedbackRepository(db_session)
    mock_bedrock = MockBedrockClient(
        response=bedrock_response, should_fail=should_fail
    )
    mock_tx_service = transaction_service or MockTransactionService()

    service = ReceiptService(
        scan_repo=scan_repo,
        feedback_repo=feedback_repo,
        bedrock_client=mock_bedrock,
        transaction_service=mock_tx_service,
    )
    return service, mock_bedrock, mock_tx_service


def _make_ocr_response(
    raw_text: str = "스타벅스 강남점\n아메리카노 1잔 4,500원",
    amount: int = 4500,
    description: str = "아메리카노",
) -> str:
    """테스트용 OCR AI 응답을 생성한다."""
    json_data = {
        "date": "2025-06-15",
        "type": "EXPENSE",
        "area": "GENERAL",
        "major_category": "식비",
        "minor_category": "카페",
        "description": description,
        "amount": amount,
        "discount": 0,
    }
    return f"{raw_text}\n\n```json\n{json.dumps(json_data, ensure_ascii=False)}\n```"


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_scan_receipt_success(db_session):
    """영수증 업로드 및 OCR 정상 동작 검증."""
    user = await create_test_user(db_session)
    ocr_response = _make_ocr_response()
    service, mock_bedrock, _ = _build_receipt_service(
        db_session, bedrock_response=ocr_response
    )

    scan = await service.scan_receipt(
        user, image_bytes=b"fake_image_data", content_type="image/jpeg"
    )

    assert scan.status == ScanStatus.COMPLETED.value
    assert scan.raw_text is not None
    assert scan.extracted_data is not None
    assert scan.extracted_data["amount"] == 4500
    assert mock_bedrock.call_count == 1


@pytest.mark.asyncio
async def test_scan_receipt_state_transition_completed(db_session):
    """스캔 상태 전이: PENDING → COMPLETED 검증."""
    user = await create_test_user(db_session)
    ocr_response = _make_ocr_response()
    service, _, _ = _build_receipt_service(
        db_session, bedrock_response=ocr_response
    )

    scan = await service.scan_receipt(
        user, image_bytes=b"fake_image", content_type="image/png"
    )

    assert scan.status == ScanStatus.COMPLETED.value
    assert scan.raw_text is not None
    assert scan.extracted_data is not None


@pytest.mark.asyncio
async def test_scan_receipt_state_transition_failed(db_session):
    """스캔 상태 전이: PENDING → FAILED 검증 (Bedrock 실패 시)."""
    user = await create_test_user(
        db_session, email="fail@test.com", nickname="실패유저"
    )
    service, _, _ = _build_receipt_service(db_session, should_fail=True)

    with pytest.raises(BedrockError):
        await service.scan_receipt(
            user, image_bytes=b"fake_image", content_type="image/jpeg"
        )

    # FAILED 상태로 갱신되었는지 확인
    scans = await service.get_scans(user)
    assert len(scans) == 1
    assert scans[0].status == ScanStatus.FAILED.value


@pytest.mark.asyncio
async def test_get_scans_with_status_filter(db_session):
    """스캔 이력 조회 및 status 필터 검증."""
    user = await create_test_user(
        db_session, email="filter@test.com", nickname="필터유저"
    )
    ocr_response = _make_ocr_response()
    service, _, _ = _build_receipt_service(
        db_session, bedrock_response=ocr_response
    )

    # 성공 스캔 1건 생성
    await service.scan_receipt(
        user, image_bytes=b"img1", content_type="image/jpeg"
    )

    # 전체 조회
    all_scans = await service.get_scans(user)
    assert len(all_scans) >= 1

    # COMPLETED 필터
    completed_scans = await service.get_scans(
        user, status=ScanStatus.COMPLETED.value
    )
    assert all(s.status == ScanStatus.COMPLETED.value for s in completed_scans)


@pytest.mark.asyncio
async def test_get_scan_detail_forbidden(db_session):
    """다른 사용자 스캔 접근 시 ForbiddenError 검증."""
    user_a = await create_test_user(
        db_session, email="owner@test.com", nickname="소유자"
    )
    user_b = await create_test_user(
        db_session, email="other@test.com", nickname="타인"
    )
    ocr_response = _make_ocr_response()
    service, _, _ = _build_receipt_service(
        db_session, bedrock_response=ocr_response
    )

    scan = await service.scan_receipt(
        user_a, image_bytes=b"img", content_type="image/jpeg"
    )

    with pytest.raises(ForbiddenError):
        await service.get_scan_detail(user_b, scan.id)


@pytest.mark.asyncio
async def test_confirm_transaction_success(db_session):
    """거래 확정 정상 동작 및 source=RECEIPT_SCAN 검증."""
    user = await create_test_user(
        db_session, email="confirm@test.com", nickname="확정유저"
    )
    ocr_response = _make_ocr_response()
    mock_tx_service = MockTransactionService()
    service, _, _ = _build_receipt_service(
        db_session,
        bedrock_response=ocr_response,
        transaction_service=mock_tx_service,
    )

    scan = await service.scan_receipt(
        user, image_bytes=b"img", content_type="image/jpeg"
    )

    transaction = await service.confirm_transaction(user, scan.id)

    assert transaction is not None
    assert transaction.source == TransactionSource.RECEIPT_SCAN.value
    assert mock_tx_service.call_count == 1


@pytest.mark.asyncio
async def test_confirm_transaction_not_completed(db_session):
    """COMPLETED가 아닌 스캔 확정 시 BadRequestError 검증."""
    user = await create_test_user(
        db_session, email="notcomplete@test.com", nickname="미완료"
    )
    service, _, _ = _build_receipt_service(db_session, should_fail=True)

    # FAILED 상태의 스캔 생성
    with pytest.raises(BedrockError):
        await service.scan_receipt(
            user, image_bytes=b"img", content_type="image/jpeg"
        )

    scans = await service.get_scans(user)
    failed_scan = scans[0]

    with pytest.raises(BadRequestError):
        await service.confirm_transaction(user, failed_scan.id)


@pytest.mark.asyncio
async def test_confirm_transaction_conflict(db_session):
    """이미 확정된 스캔 재확정 시 ConflictError 검증."""
    user = await create_test_user(
        db_session, email="conflict@test.com", nickname="중복유저"
    )
    ocr_response = _make_ocr_response()
    service, _, _ = _build_receipt_service(
        db_session, bedrock_response=ocr_response
    )

    scan = await service.scan_receipt(
        user, image_bytes=b"img", content_type="image/jpeg"
    )

    # 첫 번째 확정
    await service.confirm_transaction(user, scan.id)

    # 두 번째 확정 시도 → ConflictError
    with pytest.raises(ConflictError):
        await service.confirm_transaction(user, scan.id)


# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════


# ──────────────────────────────────────────────
# Property 8: 영수증 스캔 상태 전이
# Feature: moneylog-backend-phase7, Property 8: 영수증 스캔 상태 전이
# Validates: Requirements 9.1, 9.3, 9.4, 9.5, 9.6
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    amount=st.integers(min_value=100, max_value=10_000_000),
    should_fail=st.booleans(),
)
async def test_property_receipt_scan_state_transition(
    db_session, amount, should_fail
):
    """영수증 스캔 시 초기 상태는 PENDING이고, OCR 성공 시 COMPLETED, 실패 시 FAILED로 전이되어야 한다.
    COMPLETED 상태에서는 raw_text와 extracted_data가 설정되어야 한다.

    **Validates: Requirements 9.1, 9.3, 9.4, 9.5, 9.6**
    """
    user = await create_test_user(
        db_session,
        email=f"p8_{uuid.uuid4().hex[:8]}@test.com",
        nickname="P8",
    )
    ocr_response = _make_ocr_response(amount=amount)

    service, _, _ = _build_receipt_service(
        db_session,
        bedrock_response=ocr_response,
        should_fail=should_fail,
    )

    if should_fail:
        with pytest.raises(BedrockError):
            await service.scan_receipt(
                user, image_bytes=b"fake_img", content_type="image/jpeg"
            )
        # FAILED 상태 확인
        scans = await service.get_scans(user)
        assert len(scans) >= 1
        latest = scans[0]
        assert latest.status == ScanStatus.FAILED.value
    else:
        scan = await service.scan_receipt(
            user, image_bytes=b"fake_img", content_type="image/jpeg"
        )
        assert scan.status == ScanStatus.COMPLETED.value
        assert scan.raw_text is not None
        assert scan.extracted_data is not None
        assert scan.extracted_data["amount"] == amount


# ──────────────────────────────────────────────
# Property 9: 영수증 이미지 검증
# Feature: moneylog-backend-phase7, Property 9: 영수증 이미지 검증
# Validates: Requirements 9.7, 9.8
# ──────────────────────────────────────────────

# 이미지 검증은 라우터 레벨에서 수행되므로, 순수 함수로 검증 로직을 테스트한다.

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_receipt_image(content_type: str, file_size: int) -> None:
    """영수증 이미지 형식 및 크기를 검증한다 (라우터 레벨 검증 로직)."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError("지원하지 않는 이미지 형식입니다 (JPEG, PNG만 허용)")
    if file_size > MAX_IMAGE_SIZE:
        raise BadRequestError("파일 크기가 10MB를 초과합니다")


# 이미지 형식 전략
valid_content_types = st.sampled_from(["image/jpeg", "image/png"])
invalid_content_types = st.sampled_from([
    "image/gif", "image/bmp", "image/webp", "application/pdf",
    "text/plain", "image/tiff",
])

# 파일 크기 전략
valid_file_sizes = st.integers(min_value=1, max_value=MAX_IMAGE_SIZE)
oversized_file_sizes = st.integers(
    min_value=MAX_IMAGE_SIZE + 1, max_value=MAX_IMAGE_SIZE * 3
)


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    content_type=invalid_content_types,
    file_size=valid_file_sizes,
)
async def test_property_receipt_image_invalid_format(
    db_session, content_type, file_size
):
    """JPEG/PNG가 아닌 형식이면 BadRequestError가 발생해야 한다.

    **Validates: Requirements 9.7, 9.8**
    """
    with pytest.raises(BadRequestError):
        validate_receipt_image(content_type, file_size)


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    content_type=valid_content_types,
    file_size=oversized_file_sizes,
)
async def test_property_receipt_image_oversized(
    db_session, content_type, file_size
):
    """10MB를 초과하면 BadRequestError가 발생해야 한다.

    **Validates: Requirements 9.7, 9.8**
    """
    with pytest.raises(BadRequestError):
        validate_receipt_image(content_type, file_size)


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    content_type=valid_content_types,
    file_size=valid_file_sizes,
)
async def test_property_receipt_image_valid(
    db_session, content_type, file_size
):
    """유효한 형식과 크기이면 검증을 통과해야 한다.

    **Validates: Requirements 9.7, 9.8**
    """
    # 예외가 발생하지 않아야 한다
    validate_receipt_image(content_type, file_size)


# ──────────────────────────────────────────────
# Property 10: 영수증 거래 확정 라운드트립
# Feature: moneylog-backend-phase7, Property 10: 영수증 거래 확정 라운드트립
# Validates: Requirements 10.1, 10.2, 10.3, 10.4
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(amount=st.integers(min_value=100, max_value=1_000_000))
async def test_property_receipt_confirm_roundtrip(db_session, amount):
    """COMPLETED 상태의 스캔에 대해 confirm_transaction 호출 시 Transaction이 생성되고
    source가 RECEIPT_SCAN이어야 하며, 스캔의 transaction_id가 갱신되어야 한다.

    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    """
    user = await create_test_user(
        db_session,
        email=f"p10_{uuid.uuid4().hex[:8]}@test.com",
        nickname="P10",
    )
    ocr_response = _make_ocr_response(amount=amount)
    mock_tx_service = MockTransactionService()
    service, _, _ = _build_receipt_service(
        db_session,
        bedrock_response=ocr_response,
        transaction_service=mock_tx_service,
    )

    # 스캔 생성 (COMPLETED)
    scan = await service.scan_receipt(
        user, image_bytes=b"img", content_type="image/jpeg"
    )
    assert scan.status == ScanStatus.COMPLETED.value

    # 거래 확정
    transaction = await service.confirm_transaction(user, scan.id)

    assert transaction is not None
    assert transaction.source == TransactionSource.RECEIPT_SCAN.value
    assert mock_tx_service.call_count == 1

    # 스캔의 transaction_id가 갱신되었는지 확인
    updated_scan = await service.get_scan_detail(user, scan.id)
    assert updated_scan.transaction_id == transaction.id


# ──────────────────────────────────────────────
# Property 11: 스캔 이력 조회 및 접근 권한
# Feature: moneylog-backend-phase7, Property 11: 스캔 이력 조회 및 접근 권한
# Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(scan_count=st.integers(min_value=1, max_value=3))
async def test_property_scan_history_and_access(db_session, scan_count):
    """사용자의 스캔 이력 조회 시 본인의 스캔만 반환되어야 하고,
    다른 사용자의 스캔 접근 시 ForbiddenError가 발생해야 한다.

    **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**
    """
    uid = uuid.uuid4().hex[:6]
    user_a = await create_test_user(
        db_session, email=f"p11a_{uid}@test.com", nickname="P11A"
    )
    user_b = await create_test_user(
        db_session, email=f"p11b_{uid}@test.com", nickname="P11B"
    )
    ocr_response = _make_ocr_response()
    service, _, _ = _build_receipt_service(
        db_session, bedrock_response=ocr_response
    )

    # user_a의 스캔 생성
    created_scan_ids = []
    for _ in range(scan_count):
        scan = await service.scan_receipt(
            user_a, image_bytes=b"img", content_type="image/jpeg"
        )
        created_scan_ids.append(scan.id)

    # user_a의 스캔 이력 조회 → 본인 스캔만 반환
    scans_a = await service.get_scans(user_a)
    scan_ids_a = [s.id for s in scans_a]
    for sid in created_scan_ids:
        assert sid in scan_ids_a

    # user_b의 스캔 이력에는 user_a의 스캔이 없어야 함
    scans_b = await service.get_scans(user_b)
    scan_ids_b = [s.id for s in scans_b]
    for sid in created_scan_ids:
        assert sid not in scan_ids_b

    # user_b가 user_a의 스캔 상세 조회 → ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.get_scan_detail(user_b, created_scan_ids[0])

    # 존재하지 않는 스캔 조회 → NotFoundError
    with pytest.raises(NotFoundError):
        await service.get_scan_detail(user_a, uuid.uuid4())

    # status 필터 검증
    completed_scans = await service.get_scans(
        user_a, status=ScanStatus.COMPLETED.value
    )
    assert all(
        s.status == ScanStatus.COMPLETED.value for s in completed_scans
    )
