"""
카드 결제 주기 및 청구할인 관련 HTTP 엔드포인트.

결제 주기 설정 조회/변경, 결제 주기 조회, 결제 주기별 거래 조회,
결제 예정 금액 조회, 청구할인 CRUD를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.billing_discount_repository import BillingDiscountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.billing_cycle import (
    BillingConfigResponse,
    BillingConfigUpdateRequest,
    BillingCycleResponse,
    BillingDiscountCreateRequest,
    BillingDiscountResponse,
    BillingDiscountUpdateRequest,
    BillingSummaryResponse,
    BillingTransactionsResponse,
)
from app.services.billing_cycle_service import BillingCycleService

router = APIRouter(tags=["billing"])


def _build_service(db: AsyncSession) -> BillingCycleService:
    """DB 세션으로 BillingCycleService 인스턴스를 생성한다."""
    return BillingCycleService(
        AssetRepository(db),
        BillingDiscountRepository(db),
        TransactionRepository(db),
    )


# ──────────────────────────────────────────────
# 결제 주기 설정 조회
# ──────────────────────────────────────────────


@router.get(
    "/assets/{asset_id}/billing/config",
    response_model=BillingConfigResponse,
    summary="결제 주기 설정 조회",
)
async def get_billing_config(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingConfigResponse:
    """카드 자산의 결제 주기 설정(결제일, 사용 기준일, 현재 주기)을 조회한다."""
    service = _build_service(db)
    return await service.get_billing_config(current_user, asset_id)


# ──────────────────────────────────────────────
# 결제 주기 설정 변경
# ──────────────────────────────────────────────


@router.put(
    "/assets/{asset_id}/billing/config",
    response_model=BillingConfigResponse,
    summary="결제 주기 설정 변경",
)
async def update_billing_config(
    asset_id: UUID,
    body: BillingConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingConfigResponse:
    """카드 자산의 결제일과 사용 기준일을 변경한다."""
    service = _build_service(db)
    await service.update_billing_config(
        current_user, asset_id, body.payment_day, body.billing_start_day,
    )
    await db.commit()
    return await service.get_billing_config(current_user, asset_id)


# ──────────────────────────────────────────────
# 현재/특정 결제 주기 조회
# ──────────────────────────────────────────────


@router.get(
    "/assets/{asset_id}/billing/cycle",
    response_model=BillingCycleResponse,
    summary="결제 주기 조회",
)
async def get_billing_cycle(
    asset_id: UUID,
    reference_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingCycleResponse:
    """현재 또는 특정 기준일의 결제 주기(시작일, 종료일, 결제 예정일)를 조회한다."""
    service = _build_service(db)
    return await service.get_billing_cycle(current_user, asset_id, reference_date)


# ──────────────────────────────────────────────
# 결제 주기별 거래 조회
# ──────────────────────────────────────────────


@router.get(
    "/assets/{asset_id}/billing/transactions",
    response_model=BillingTransactionsResponse,
    summary="결제 주기별 거래 조회",
)
async def get_billing_transactions(
    asset_id: UUID,
    reference_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingTransactionsResponse:
    """결제 주기에 해당하는 거래 목록을 조회한다."""
    service = _build_service(db)
    return await service.get_billing_transactions(
        current_user, asset_id, reference_date,
    )


# ──────────────────────────────────────────────
# 결제 예정 금액 조회
# ──────────────────────────────────────────────


@router.get(
    "/assets/{asset_id}/billing/summary",
    response_model=BillingSummaryResponse,
    summary="결제 예정 금액 조회",
)
async def get_billing_summary(
    asset_id: UUID,
    reference_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingSummaryResponse:
    """결제 예정 금액(총 사용, 청구할인, 최종 결제 예정액)을 조회한다."""
    service = _build_service(db)
    return await service.get_billing_summary(
        current_user, asset_id, reference_date,
    )


# ──────────────────────────────────────────────
# 청구할인 등록
# ──────────────────────────────────────────────


@router.post(
    "/assets/{asset_id}/billing/discounts",
    response_model=BillingDiscountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="청구할인 등록",
)
async def create_billing_discount(
    asset_id: UUID,
    body: BillingDiscountCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingDiscountResponse:
    """카드 자산에 청구할인을 등록한다."""
    service = _build_service(db)
    discount = await service.create_discount(current_user, asset_id, body)
    await db.commit()
    return BillingDiscountResponse.model_validate(discount)


# ──────────────────────────────────────────────
# 청구할인 수정
# ──────────────────────────────────────────────


@router.put(
    "/billing/discounts/{discount_id}",
    response_model=BillingDiscountResponse,
    summary="청구할인 수정",
)
async def update_billing_discount(
    discount_id: UUID,
    body: BillingDiscountUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingDiscountResponse:
    """청구할인 정보를 수정한다."""
    service = _build_service(db)
    discount = await service.update_discount(current_user, discount_id, body)
    await db.commit()
    return BillingDiscountResponse.model_validate(discount)


# ──────────────────────────────────────────────
# 청구할인 삭제
# ──────────────────────────────────────────────


@router.delete(
    "/billing/discounts/{discount_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="청구할인 삭제",
)
async def delete_billing_discount(
    discount_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """청구할인을 삭제한다."""
    service = _build_service(db)
    await service.delete_discount(current_user, discount_id)
    await db.commit()
