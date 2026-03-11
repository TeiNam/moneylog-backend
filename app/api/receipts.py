"""
영수증(Receipt) OCR 관련 HTTP 엔드포인트.

영수증 이미지 업로드 및 OCR 분석, 스캔 이력 조회,
스캔 상세 조회, OCR 결과 거래 확정을 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import BadRequestError
from app.models.user import User
from app.repositories.ai_feedback_repository import AIFeedbackRepository
from app.repositories.ceremony_person_repository import CeremonyPersonRepository
from app.repositories.receipt_scan_repository import ReceiptScanRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.receipt import ReceiptConfirmRequest, ReceiptScanResponse
from app.schemas.transaction import TransactionResponse
from app.services.bedrock_client import BedrockClient, BedrockError
from app.services.receipt_service import ReceiptService
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/ai/receipts", tags=["receipts"])


def _build_service(db: AsyncSession) -> ReceiptService:
    """DB 세션으로 ReceiptService 인스턴스를 생성한다."""
    return ReceiptService(
        scan_repo=ReceiptScanRepository(db),
        feedback_repo=AIFeedbackRepository(db),
        bedrock_client=BedrockClient(),
        transaction_service=TransactionService(
            TransactionRepository(db),
            CeremonyPersonRepository(db),
        ),
    )


# ──────────────────────────────────────────────
# 영수증 이미지 업로드 및 OCR
# ──────────────────────────────────────────────


@router.post(
    "/scan",
    response_model=ReceiptScanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="영수증 이미지 업로드 및 OCR",
)
async def scan_receipt(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptScanResponse | JSONResponse:
    """영수증 이미지를 업로드하고 OCR 분석을 수행한다."""
    # 이미지 형식 검증
    if file.content_type not in ("image/jpeg", "image/png"):
        raise BadRequestError("지원하지 않는 이미지 형식입니다 (JPEG, PNG만 허용)")

    # 이미지 바이트 읽기 및 크기 검증
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise BadRequestError("파일 크기가 10MB를 초과합니다")

    service = _build_service(db)
    try:
        scan = await service.scan_receipt(
            current_user, image_bytes, file.content_type
        )
        await db.commit()
        return ReceiptScanResponse.model_validate(scan)
    except BedrockError as e:
        await db.commit()
        return JSONResponse(status_code=502, content={"detail": e.detail})


# ──────────────────────────────────────────────
# 스캔 이력 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[ReceiptScanResponse],
    summary="스캔 이력 목록 조회",
)
async def list_scans(
    status_filter: str | None = Query(None, alias="status", description="스캔 상태 필터"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReceiptScanResponse]:
    """현재 사용자의 영수증 스캔 이력을 최신순으로 조회한다."""
    service = _build_service(db)
    scans = await service.get_scans(current_user, status=status_filter)
    return [ReceiptScanResponse.model_validate(s) for s in scans]


# ──────────────────────────────────────────────
# 스캔 상세 조회
# ──────────────────────────────────────────────


@router.get(
    "/{scan_id}",
    response_model=ReceiptScanResponse,
    summary="스캔 상세 조회",
)
async def get_scan_detail(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptScanResponse:
    """영수증 스캔 상세 정보를 조회한다."""
    service = _build_service(db)
    scan = await service.get_scan_detail(current_user, scan_id)
    return ReceiptScanResponse.model_validate(scan)


# ──────────────────────────────────────────────
# OCR 결과 거래 확정
# ──────────────────────────────────────────────


@router.post(
    "/{scan_id}/confirm",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="OCR 결과 거래 확정",
)
async def confirm_transaction(
    scan_id: UUID,
    body: ReceiptConfirmRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    """OCR로 추출된 거래 데이터를 확정하여 Transaction을 생성한다."""
    service = _build_service(db)
    overrides = (
        body.overrides.model_dump(exclude_none=True)
        if body and body.overrides
        else None
    )
    transaction = await service.confirm_transaction(
        current_user, scan_id, overrides
    )
    await db.commit()
    return TransactionResponse.model_validate(transaction)
