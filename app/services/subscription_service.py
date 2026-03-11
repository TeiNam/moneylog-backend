"""
구독(Subscription) 비즈니스 로직 서비스.

구독 CRUD, 월 구독료 합계/연환산 금액 계산, 다음 결제일 계산을 담당한다.
소유권 기반 권한 검증(본인 소유 확인)을 수행한다.
"""

import calendar
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import SubscriptionCycle, SubscriptionStatus
from app.models.notification import Notification
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import (
    SubscriptionCreateRequest,
    SubscriptionDetailResponse,
    SubscriptionSummaryResponse,
    SubscriptionUpdateRequest,
)

logger = logging.getLogger(__name__)


class SubscriptionService:
    """구독 CRUD, 요약 계산, 다음 결제일 계산 서비스."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        notification_repo: NotificationRepository | None = None,
    ) -> None:
        self._repo = subscription_repo
        self._notification_repo = notification_repo

    # ──────────────────────────────────────────────
    # 구독 생성
    # ──────────────────────────────────────────────

    async def create(
        self, user: User, data: SubscriptionCreateRequest
    ) -> Subscription:
        """새 구독을 생성한다. user_id는 현재 사용자로 자동 설정.

        Args:
            user: 현재 인증된 사용자
            data: 구독 생성 요청 데이터

        Returns:
            생성된 Subscription 객체
        """
        subscription_data = data.model_dump()
        subscription_data["user_id"] = user.id
        subscription_data["family_group_id"] = user.family_group_id

        # Enum 값을 문자열로 변환
        for field in ("category", "cycle", "status"):
            value = subscription_data.get(field)
            if value is not None and hasattr(value, "value"):
                subscription_data[field] = value.value

        subscription = await self._repo.create(subscription_data)
        logger.info("구독 생성 완료: subscription_id=%s", subscription.id)
        return subscription

    # ──────────────────────────────────────────────
    # 구독 목록 조회
    # ──────────────────────────────────────────────

    async def get_list(
        self, user: User, status: SubscriptionStatus | None = None
    ) -> list[Subscription]:
        """사용자의 구독 목록을 반환한다. status 필터 선택 적용.

        Args:
            user: 현재 인증된 사용자
            status: 구독 상태 필터 (None이면 전체 조회)

        Returns:
            구독 목록
        """
        status_value = status.value if status is not None else None
        return await self._repo.get_list_by_user(user.id, status=status_value)

    # ──────────────────────────────────────────────
    # 구독 상세 조회
    # ──────────────────────────────────────────────

    async def get_detail(
        self, user: User, subscription_id: UUID
    ) -> SubscriptionDetailResponse:
        """구독 상세 정보를 다음 결제일과 함께 반환한다.

        Args:
            user: 현재 인증된 사용자
            subscription_id: 조회할 구독 ID

        Returns:
            다음 결제일이 포함된 구독 상세 응답

        Raises:
            NotFoundError: 구독이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        subscription = await self._repo.get_by_id(subscription_id)
        if subscription is None:
            raise NotFoundError("구독을 찾을 수 없습니다")

        self._check_permission(user, subscription)

        # 다음 결제일 계산
        next_billing_date = self.calculate_next_billing_date(
            subscription, date.today()
        )

        return SubscriptionDetailResponse(
            id=subscription.id,
            user_id=subscription.user_id,
            family_group_id=subscription.family_group_id,
            service_name=subscription.service_name,
            category=subscription.category,
            amount=subscription.amount,
            cycle=subscription.cycle,
            billing_day=subscription.billing_day,
            asset_id=subscription.asset_id,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            status=subscription.status,
            notify_before_days=subscription.notify_before_days,
            memo=subscription.memo,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
            next_billing_date=next_billing_date,
        )

    # ──────────────────────────────────────────────
    # 구독 수정
    # ──────────────────────────────────────────────

    async def update(
        self,
        user: User,
        subscription_id: UUID,
        data: SubscriptionUpdateRequest,
    ) -> Subscription:
        """구독 정보를 갱신한다. 권한 검증 포함.

        Args:
            user: 현재 인증된 사용자
            subscription_id: 수정할 구독 ID
            data: 구독 수정 요청 데이터

        Returns:
            갱신된 Subscription 객체

        Raises:
            NotFoundError: 구독이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        subscription = await self._repo.get_by_id(subscription_id)
        if subscription is None:
            raise NotFoundError("구독을 찾을 수 없습니다")

        self._check_permission(user, subscription)

        # None이 아닌 필드만 업데이트 딕셔너리에 포함
        update_data: dict = {}
        for field in (
            "service_name",
            "category",
            "amount",
            "cycle",
            "billing_day",
            "asset_id",
            "start_date",
            "end_date",
            "status",
            "notify_before_days",
            "memo",
        ):
            value = getattr(data, field, None)
            if value is not None:
                # Enum 값은 문자열로 변환
                update_data[field] = (
                    value.value if hasattr(value, "value") else value
                )

        # updated_at 설정
        update_data["updated_at"] = datetime.now(timezone.utc)

        updated = await self._repo.update(subscription_id, update_data)
        logger.info("구독 수정 완료: subscription_id=%s", subscription_id)
        return updated

    # ──────────────────────────────────────────────
    # 구독 삭제
    # ──────────────────────────────────────────────

    async def delete(self, user: User, subscription_id: UUID) -> None:
        """구독을 삭제한다. 권한 검증 포함.

        Args:
            user: 현재 인증된 사용자
            subscription_id: 삭제할 구독 ID

        Raises:
            NotFoundError: 구독이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        subscription = await self._repo.get_by_id(subscription_id)
        if subscription is None:
            raise NotFoundError("구독을 찾을 수 없습니다")

        self._check_permission(user, subscription)

        await self._repo.delete(subscription_id)
        logger.info("구독 삭제 완료: subscription_id=%s", subscription_id)

    # ──────────────────────────────────────────────
    # 구독 요약
    # ──────────────────────────────────────────────

    async def get_summary(self, user: User) -> SubscriptionSummaryResponse:
        """활성 구독의 월 구독료 합계와 연환산 금액을 반환한다.

        Args:
            user: 현재 인증된 사용자

        Returns:
            월 구독료 합계, 연환산 금액, 활성 구독 수
        """
        active_subscriptions = await self._repo.get_list_by_user(
            user.id, status=SubscriptionStatus.ACTIVE.value
        )

        monthly_total = sum(
            self.calculate_monthly_amount(sub) for sub in active_subscriptions
        )
        yearly_total = monthly_total * 12
        active_count = len(active_subscriptions)

        return SubscriptionSummaryResponse(
            monthly_total=monthly_total,
            yearly_total=yearly_total,
            active_count=active_count,
        )

    # ──────────────────────────────────────────────
    # 다음 결제일 계산
    # ──────────────────────────────────────────────

    def calculate_next_billing_date(
        self, subscription: Subscription, reference_date: date
    ) -> date | None:
        """구독의 다음 결제일을 계산한다.

        - MONTHLY: reference_date 기준 이번 달 또는 다음 달의 billing_day
          (billing_day가 해당 월 마지막 날보다 크면 마지막 날로 클램핑)
        - YEARLY: start_date의 월 + billing_day 기준으로 다음 결제일
        - WEEKLY: start_date의 요일 기준으로 다음 결제일

        Args:
            subscription: 구독 객체
            reference_date: 기준 날짜

        Returns:
            다음 결제일 (계산 불가 시 None)
        """
        cycle = subscription.cycle
        billing_day = subscription.billing_day
        start_date = subscription.start_date

        if cycle == SubscriptionCycle.MONTHLY.value:
            # 이번 달 billing_day 시도
            last_day = calendar.monthrange(reference_date.year, reference_date.month)[1]
            clamped_day = min(billing_day, last_day)
            candidate = reference_date.replace(day=clamped_day)
            if candidate >= reference_date:
                return candidate
            # 다음 달로 이동
            if reference_date.month == 12:
                next_month = reference_date.replace(
                    year=reference_date.year + 1, month=1, day=1
                )
            else:
                next_month = reference_date.replace(
                    month=reference_date.month + 1, day=1
                )
            last_day = calendar.monthrange(next_month.year, next_month.month)[1]
            clamped_day = min(billing_day, last_day)
            return next_month.replace(day=clamped_day)

        elif cycle == SubscriptionCycle.YEARLY.value:
            # start_date의 월과 billing_day 기준
            target_month = start_date.month
            last_day = calendar.monthrange(reference_date.year, target_month)[1]
            clamped_day = min(billing_day, last_day)
            candidate = date(reference_date.year, target_month, clamped_day)
            if candidate >= reference_date:
                return candidate
            # 내년으로 이동
            last_day = calendar.monthrange(reference_date.year + 1, target_month)[1]
            clamped_day = min(billing_day, last_day)
            return date(reference_date.year + 1, target_month, clamped_day)

        elif cycle == SubscriptionCycle.WEEKLY.value:
            # start_date의 요일 기준
            target_weekday = start_date.weekday()
            days_ahead = target_weekday - reference_date.weekday()
            if days_ahead < 0:
                days_ahead += 7
            if days_ahead == 0:
                return reference_date
            return reference_date + timedelta(days=days_ahead)

        return None

    # ──────────────────────────────────────────────
    # 월 환산 금액 계산
    # ──────────────────────────────────────────────

    def calculate_monthly_amount(self, subscription: Subscription) -> int:
        """구독의 월 환산 금액을 계산한다.

        - MONTHLY: amount 그대로
        - YEARLY: amount // 12 (정수 내림)
        - WEEKLY: amount * 4

        Args:
            subscription: 구독 객체

        Returns:
            월 환산 금액
        """
        cycle = subscription.cycle
        amount = subscription.amount

        if cycle == SubscriptionCycle.MONTHLY.value:
            return amount
        elif cycle == SubscriptionCycle.YEARLY.value:
            return amount // 12
        elif cycle == SubscriptionCycle.WEEKLY.value:
            return amount * 4
        return 0

    # ──────────────────────────────────────────────
    # 권한 검증
    # ──────────────────────────────────────────────

    def _check_permission(self, user: User, subscription: Subscription) -> None:
        """사용자가 해당 구독에 접근할 권한이 있는지 검증한다.

        본인 소유 구독인 경우만 허용한다.

        Raises:
            ForbiddenError: 접근 권한이 없을 때
        """
        if subscription.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

    # ──────────────────────────────────────────────
    # 알림 조회
    # ──────────────────────────────────────────────

    async def get_notifications(self, user: User) -> list[Notification]:
        """사용자의 알림 목록을 최신순으로 반환한다.

        Args:
            user: 현재 인증된 사용자

        Returns:
            최신순(created_at 내림차순)으로 정렬된 알림 목록
        """
        return await self._notification_repo.get_list_by_user(user.id)

    # ──────────────────────────────────────────────
    # 알림 읽음 처리
    # ──────────────────────────────────────────────

    async def mark_notification_read(
        self, user: User, notification_id: UUID
    ) -> Notification:
        """알림을 읽음 처리한다. 권한 검증 포함.

        Args:
            user: 현재 인증된 사용자
            notification_id: 읽음 처리할 알림 ID

        Returns:
            갱신된 Notification 객체

        Raises:
            NotFoundError: 알림이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        notification = await self._notification_repo.get_by_id(notification_id)
        if notification is None:
            raise NotFoundError("알림을 찾을 수 없습니다")

        if notification.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

        updated = await self._notification_repo.update(
            notification_id, {"is_read": True}
        )
        return updated
