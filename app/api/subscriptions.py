"""
구독(Subscription) 관련 HTTP 엔드포인트.

구독 생성, 목록 조회, 요약, 상세 조회, 수정, 삭제,
배치 결제 자동 생성, 결제 전 알림 배치를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, verify_batch_api_key
from app.models.enums import SubscriptionStatus
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.subscription import (
    BatchNotifyResult,
    BatchProcessRequest,
    BatchProcessResult,
    SubscriptionCreateRequest,
    SubscriptionDetailResponse,
    SubscriptionResponse,
    SubscriptionSummaryResponse,
    SubscriptionUpdateRequest,
)
from app.services.subscription_batch_service import SubscriptionBatchService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _build_service(db: AsyncSession) -> SubscriptionService:
    """DB 세션으로 SubscriptionService 인스턴스를 생성한다."""
    return SubscriptionService(
        SubscriptionRepository(db),
        notification_repo=NotificationRepository(db),
    )


def _build_batch_service(db: AsyncSession) -> SubscriptionBatchService:
    """DB 세션으로 SubscriptionBatchService 인스턴스를 생성한다."""
    return SubscriptionBatchService(
        SubscriptionRepository(db),
        TransactionRepository(db),
        NotificationRepository(db),
    )


# ──────────────────────────────────────────────
# 구독 생성
# ──────────────────────────────────────────────


@router.post(
    "/",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="구독 생성",
)
async def create_subscription(
    body: SubscriptionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """새로운 구독을 생성한다."""
    service = _build_service(db)
    subscription = await service.create(current_user, body)
    await db.commit()
    return SubscriptionResponse.model_validate(subscription)


# ──────────────────────────────────────────────
# 구독 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[SubscriptionResponse],
    summary="구독 목록 조회",
)
async def list_subscriptions(
    status_filter: SubscriptionStatus | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubscriptionResponse]:
    """사용자의 구독 목록을 조회한다. status 쿼리 파라미터로 필터링 가능."""
    service = _build_service(db)
    subscriptions = await service.get_list(current_user, status=status_filter)
    return [SubscriptionResponse.model_validate(s) for s in subscriptions]


# ──────────────────────────────────────────────
# 구독 요약 (/{id} 경로보다 먼저 정의)
# ──────────────────────────────────────────────


@router.get(
    "/summary",
    response_model=SubscriptionSummaryResponse,
    summary="구독 요약 조회",
)
async def get_subscription_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionSummaryResponse:
    """활성 구독의 월 구독료 합계, 연환산 금액, 활성 구독 수를 조회한다."""
    service = _build_service(db)
    return await service.get_summary(current_user)


# ──────────────────────────────────────────────
# 배치 결제 자동 생성 (/{id} 경로보다 먼저 정의)
# ──────────────────────────────────────────────


@router.post(
    "/batch/process",
    response_model=BatchProcessResult,
    summary="구독 결제 자동 생성 배치",
)
async def batch_process_subscriptions(
    body: BatchProcessRequest,
    _api_key: None = Depends(verify_batch_api_key),  # 배치 API 키 인증
    db: AsyncSession = Depends(get_db),
) -> BatchProcessResult:
    """결제일 도래 구독에 대해 거래를 자동 생성한다. (관리자 API 키 인증 필요)"""
    batch_service = _build_batch_service(db)
    result = await batch_service.process_subscriptions(target_date=body.target_date)
    await db.commit()
    return result


# ──────────────────────────────────────────────
# 배치 결제 전 알림 (/{id} 경로보다 먼저 정의)
# ──────────────────────────────────────────────


@router.post(
    "/batch/notify",
    response_model=BatchNotifyResult,
    summary="결제 전 알림 배치",
)
async def batch_notify_subscriptions(
    _api_key: None = Depends(verify_batch_api_key),  # 배치 API 키 인증
    db: AsyncSession = Depends(get_db),
) -> BatchNotifyResult:
    """결제 전 알림 대상 구독에 대해 알림 데이터를 생성한다. (관리자 API 키 인증 필요)"""
    batch_service = _build_batch_service(db)
    result = await batch_service.process_notifications()
    await db.commit()
    return result


# ──────────────────────────────────────────────
# 구독 상세 조회
# ──────────────────────────────────────────────


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionDetailResponse,
    summary="구독 상세 조회",
)
async def get_subscription_detail(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetailResponse:
    """구독 상세 정보를 다음 결제일과 함께 조회한다."""
    service = _build_service(db)
    return await service.get_detail(current_user, subscription_id)


# ──────────────────────────────────────────────
# 구독 수정
# ──────────────────────────────────────────────


@router.put(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="구독 수정",
)
async def update_subscription(
    subscription_id: UUID,
    body: SubscriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """구독 정보를 수정한다."""
    service = _build_service(db)
    subscription = await service.update(current_user, subscription_id, body)
    await db.commit()
    return SubscriptionResponse.model_validate(subscription)


# ──────────────────────────────────────────────
# 구독 삭제
# ──────────────────────────────────────────────


@router.delete(
    "/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="구독 삭제",
)
async def delete_subscription(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """구독을 삭제한다."""
    service = _build_service(db)
    await service.delete(current_user, subscription_id)
    await db.commit()
