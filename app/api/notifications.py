"""
알림(Notification) 관련 HTTP 엔드포인트.

알림 목록 조회, 읽음 처리를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.notification import NotificationResponse
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _build_service(db: AsyncSession) -> SubscriptionService:
    """DB 세션으로 SubscriptionService 인스턴스를 생성한다."""
    return SubscriptionService(
        SubscriptionRepository(db),
        notification_repo=NotificationRepository(db),
    )


# ──────────────────────────────────────────────
# 알림 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[NotificationResponse],
    summary="알림 목록 조회",
)
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationResponse]:
    """사용자의 알림 목록을 최신순으로 조회한다."""
    service = _build_service(db)
    notifications = await service.get_notifications(current_user)
    return [NotificationResponse.model_validate(n) for n in notifications]


# ──────────────────────────────────────────────
# 알림 읽음 처리
# ──────────────────────────────────────────────


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="알림 읽음 처리",
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """알림을 읽음 처리한다."""
    service = _build_service(db)
    notification = await service.mark_notification_read(current_user, notification_id)
    await db.commit()
    return NotificationResponse.model_validate(notification)
