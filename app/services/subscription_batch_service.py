"""
구독 결제 자동 생성 배치 서비스.

결제일 도래 구독에 대해 거래를 자동 생성하고,
누락분 보정 및 결제 전 알림 데이터 생성을 담당한다.
"""

import calendar
import logging
from datetime import date, timedelta

from app.models.enums import SubscriptionCycle, SubscriptionStatus
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.subscription import BatchNotifyResult, BatchProcessResult
from app.schemas.transaction import TransactionCreateData

logger = logging.getLogger(__name__)


class SubscriptionBatchService:
    """구독 결제 자동 생성 및 알림 배치 서비스."""

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        transaction_repo: TransactionRepository,
        notification_repo: NotificationRepository,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._transaction_repo = transaction_repo
        self._notification_repo = notification_repo

    # ──────────────────────────────────────────────
    # 배치 결제 자동 생성
    # ──────────────────────────────────────────────

    async def process_subscriptions(
        self, target_date: date | None = None
    ) -> BatchProcessResult:
        """결제일 도래 구독에 대해 거래를 자동 생성한다. 누락분 보정 포함.

        target_date가 None이면 어제~오늘(2일) 범위를 처리한다.
        target_date가 지정되면 해당 날짜만 처리한다.

        Args:
            target_date: 처리 대상 날짜 (None이면 어제~오늘)

        Returns:
            배치 처리 결과 (처리 건수, 건너뛴 건수, 대상 날짜)
        """
        # 처리 대상 날짜 범위 결정
        if target_date is not None:
            dates_to_process = [target_date]
        else:
            today = date.today()
            yesterday = today - timedelta(days=1)
            dates_to_process = [yesterday, today]

        # 모든 ACTIVE 구독 조회
        active_subscriptions = await self._subscription_repo.get_active_subscriptions()

        processed_count = 0
        skipped_count = 0

        for processing_date in dates_to_process:
            for subscription in active_subscriptions:
                # 결제일 매칭 확인
                if not self._is_billing_day(subscription, processing_date):
                    continue

                # 거래 생성 시도 (중복 방지 포함)
                transaction = await self._create_transaction_for_subscription(
                    subscription, processing_date
                )
                if transaction is not None:
                    processed_count += 1
                else:
                    skipped_count += 1

        # 결과의 target_date는 마지막 처리 날짜
        result_date = dates_to_process[-1] if dates_to_process else date.today()

        return BatchProcessResult(
            processed_count=processed_count,
            skipped_count=skipped_count,
            target_date=result_date,
        )

    # ──────────────────────────────────────────────
    # 결제일 판단
    # ──────────────────────────────────────────────

    def _is_billing_day(self, subscription: Subscription, target_date: date) -> bool:
        """해당 날짜가 구독의 결제일인지 판단한다.

        - MONTHLY: billing_day가 target_date.day와 일치 (월말 클램핑 적용)
        - YEARLY: start_date.month가 일치하고 billing_day가 일치 (월말 클램핑 적용)
        - WEEKLY: start_date.weekday()가 target_date.weekday()와 일치

        Args:
            subscription: 구독 객체
            target_date: 판단 대상 날짜

        Returns:
            결제일이면 True
        """
        cycle = subscription.cycle
        billing_day = subscription.billing_day

        # Enum 인스턴스 직접 비교 (str, Enum 다중 상속으로 .value 불필요)
        if cycle == SubscriptionCycle.MONTHLY:
            # 해당 월의 마지막 날 계산
            last_day = calendar.monthrange(target_date.year, target_date.month)[1]
            # billing_day가 마지막 날보다 크면 마지막 날로 클램핑
            clamped_day = min(billing_day, last_day)
            return target_date.day == clamped_day

        elif cycle == SubscriptionCycle.YEARLY:
            # start_date의 월이 일치해야 함
            if subscription.start_date.month != target_date.month:
                return False
            # 해당 월의 마지막 날 계산 후 클램핑
            last_day = calendar.monthrange(target_date.year, target_date.month)[1]
            clamped_day = min(billing_day, last_day)
            return target_date.day == clamped_day

        elif cycle == SubscriptionCycle.WEEKLY:
            # start_date의 요일과 일치하는지 확인
            return subscription.start_date.weekday() == target_date.weekday()

        return False

    # ──────────────────────────────────────────────
    # 거래 생성
    # ──────────────────────────────────────────────

    async def _create_transaction_for_subscription(
        self, subscription: Subscription, billing_date: date
    ) -> Transaction | None:
        """구독에 대한 거래를 생성한다. 중복이면 None 반환.

        Args:
            subscription: 구독 객체
            billing_date: 결제일

        Returns:
            생성된 Transaction 객체, 중복이면 None
        """
        # 중복 확인
        exists = await self._transaction_repo.exists_subscription_auto(
            user_id=subscription.user_id,
            description=subscription.service_name,
            billing_date=billing_date,
        )
        if exists:
            return None

        # Pydantic 모델로 거래 데이터 구성
        transaction_data = TransactionCreateData(
            user_id=subscription.user_id,
            family_group_id=subscription.family_group_id,
            date=billing_date,
            area="SUBSCRIPTION",
            type="EXPENSE",
            major_category="구독",
            minor_category=subscription.category,
            description=subscription.service_name,
            amount=subscription.amount,
            discount=0,
            actual_amount=subscription.amount,
            asset_id=subscription.asset_id,
            memo=None,
            source="SUBSCRIPTION_AUTO",
        )

        transaction = await self._transaction_repo.create(transaction_data)
        logger.info(
            "구독 자동 거래 생성: subscription=%s, date=%s, transaction=%s",
            subscription.service_name,
            billing_date,
            transaction.id,
        )
        return transaction

    # ──────────────────────────────────────────────
    # 결제 전 알림 배치
    # ──────────────────────────────────────────────

    async def process_notifications(
        self, reference_date: date | None = None
    ) -> BatchNotifyResult:
        """결제 전 알림 대상 구독에 대해 알림 데이터를 생성한다.

        각 활성 구독의 notify_before_days 값을 기준으로 알림 대상을 조회하고,
        다음 결제일이 reference_date로부터 notify_before_days 이내인 구독에 대해 알림을 생성한다.

        Args:
            reference_date: 기준 날짜 (None이면 오늘)

        Returns:
            알림 배치 결과 (알림 생성 건수, 건너뛴 건수)
        """
        if reference_date is None:
            reference_date = date.today()

        active_subscriptions = await self._subscription_repo.get_active_subscriptions()

        notified_count = 0
        skipped_count = 0

        for subscription in active_subscriptions:
            # 다음 결제일 계산 (SubscriptionService 로직 재사용)
            next_billing = self._calculate_next_billing_date(
                subscription, reference_date
            )
            if next_billing is None:
                continue

            # notify_before_days 이내인지 확인
            days_until_billing = (next_billing - reference_date).days
            if days_until_billing < 0 or days_until_billing > subscription.notify_before_days:
                continue

            # 동일 결제 주기 내 중복 알림 확인
            # 알림의 created_at은 실제 배치 실행 시점(현재 시각)이므로,
            # reference_date와 다를 수 있음. 따라서 결제 주기 시작부터
            # 충분히 넓은 범위로 조회하여 중복을 감지함.
            period_start = next_billing - timedelta(
                days=subscription.notify_before_days + 1
            )
            period_end = date.today() + timedelta(days=1)

            exists = await self._notification_repo.exists_for_subscription_period(
                subscription_id=subscription.id,
                start_date=period_start,
                end_date=period_end,
            )
            if exists:
                skipped_count += 1
                continue

            # 알림 생성
            remaining_days = days_until_billing
            notification_data = {
                "user_id": subscription.user_id,
                "subscription_id": subscription.id,
                "type": "SUBSCRIPTION_PAYMENT",
                "title": "구독 결제 예정",
                "message": (
                    f"{subscription.service_name} "
                    f"{subscription.amount}원 결제 예정 "
                    f"(D-{remaining_days})"
                ),
                "is_read": False,
            }
            await self._notification_repo.create(notification_data)
            notified_count += 1

        return BatchNotifyResult(
            notified_count=notified_count,
            skipped_count=skipped_count,
        )

    # ──────────────────────────────────────────────
    # 다음 결제일 계산 (SubscriptionService 로직 재사용)
    # ──────────────────────────────────────────────

    def _calculate_next_billing_date(
        self, subscription: Subscription, reference_date: date
    ) -> date | None:
        """구독의 다음 결제일을 계산한다.

        SubscriptionService.calculate_next_billing_date와 동일한 로직.
        - MONTHLY: reference_date 기준 이번 달 또는 다음 달의 billing_day (월말 클램핑)
        - YEARLY: start_date의 월 + billing_day 기준
        - WEEKLY: start_date의 요일 기준

        Args:
            subscription: 구독 객체
            reference_date: 기준 날짜

        Returns:
            다음 결제일 (계산 불가 시 None)
        """
        cycle = subscription.cycle
        billing_day = subscription.billing_day
        start_date = subscription.start_date

        # Enum 인스턴스 직접 비교 (str, Enum 다중 상속으로 .value 불필요)
        if cycle == SubscriptionCycle.MONTHLY:
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

        elif cycle == SubscriptionCycle.YEARLY:
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

        elif cycle == SubscriptionCycle.WEEKLY:
            # start_date의 요일 기준
            target_weekday = start_date.weekday()
            days_ahead = target_weekday - reference_date.weekday()
            if days_ahead < 0:
                days_ahead += 7
            if days_ahead == 0:
                return reference_date
            return reference_date + timedelta(days=days_ahead)

        return None
