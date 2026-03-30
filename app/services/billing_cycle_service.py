"""
카드 결제 주기 및 청구할인 비즈니스 로직 서비스.

결제 주기 설정, 청구할인 CRUD, 결제 주기별 거래 조회,
결제 예정 금액 계산을 담당한다.
소유권 기반 권한 검증(개인 자산: 본인만, 공유 자산: 그룹 소속 확인)을 수행한다.
"""

import logging
from datetime import date, datetime, timezone
from uuid import UUID

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.asset import Asset
from app.models.billing_discount import BillingDiscount
from app.models.enums import AssetType, Ownership
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.billing_discount_repository import BillingDiscountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.billing_cycle import (
    BillingConfigResponse,
    BillingCycleResponse,
    BillingDiscountCreateRequest,
    BillingDiscountUpdateRequest,
    BillingSummaryResponse,
    BillingTransactionsResponse,
)
from app.schemas.transaction import TransactionResponse
from app.utils.billing_cycle_utils import (
    get_billing_cycle as calc_billing_cycle,
    get_default_billing_start_day,
    get_next_payment_date,
)

logger = logging.getLogger(__name__)

# 결제 주기 설정이 허용되는 카드 유형
_CARD_ASSET_TYPES = {AssetType.CREDIT_CARD, AssetType.DEBIT_CARD}


def _row_to_transaction_response(row) -> TransactionResponse:
    """TransactionRepository.get_list()가 반환하는 Row 객체를 TransactionResponse로 변환한다."""
    return TransactionResponse(
        id=row.id,
        user_id=row.user_id,
        family_group_id=row.family_group_id,
        date=row.date,
        area=row.area,
        type=row.type,
        major_category=row.major_category,
        minor_category=row.minor_category,
        description=row.description,
        amount=row.amount,
        discount=row.discount,
        actual_amount=row.actual_amount,
        asset_id=row.asset_id,
        memo=row.memo,
        source=row.source,
        created_at=row.created_at,
        updated_at=row.updated_at,
        is_private=row.is_private,
    )


class BillingCycleService:
    """카드 결제 주기 설정, 청구할인 관리, 결제 예정 금액 계산 서비스."""

    def __init__(
        self,
        asset_repo: AssetRepository,
        billing_discount_repo: BillingDiscountRepository,
        transaction_repo: TransactionRepository,
    ) -> None:
        self._asset_repo = asset_repo
        self._billing_discount_repo = billing_discount_repo
        self._transaction_repo = transaction_repo

    # ──────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────

    def _check_permission(self, user: User, asset: Asset) -> None:
        """사용자가 해당 자산에 접근할 권한이 있는지 검증한다.

        - 개인 자산(PERSONAL): 본인 소유인 경우만 허용
        - 공유 자산(SHARED): 같은 가족 그룹에 소속된 경우만 허용

        Raises:
            ForbiddenError: 접근 권한이 없을 때
        """
        if asset.ownership == Ownership.PERSONAL and asset.user_id == user.id:
            return
        if (
            asset.ownership == Ownership.SHARED
            and user.family_group_id is not None
            and asset.family_group_id == user.family_group_id
        ):
            return
        raise ForbiddenError("접근 권한이 없습니다")

    async def _validate_card_asset(self, user: User, asset_id: UUID) -> Asset:
        """자산 존재 확인 + 카드 유형 검증 + 소유권 확인 헬퍼.

        Args:
            user: 현재 인증된 사용자
            asset_id: 검증할 자산 ID

        Returns:
            검증된 Asset 객체

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            BadRequestError: 카드 유형이 아닐 때
            ForbiddenError: 접근 권한이 없을 때
        """
        asset = await self._asset_repo.get_by_id(asset_id)
        if asset is None:
            raise NotFoundError("자산을 찾을 수 없습니다")

        # 카드 유형 검증
        if asset.asset_type not in {t.value for t in _CARD_ASSET_TYPES}:
            raise BadRequestError("카드 유형 자산만 결제 주기를 설정할 수 있습니다")

        # 소유권 검증
        self._check_permission(user, asset)
        return asset

    # ──────────────────────────────────────────────
    # 결제 주기 설정
    # ──────────────────────────────────────────────

    async def update_billing_config(
        self,
        user: User,
        asset_id: UUID,
        payment_day: int,
        billing_start_day: int | None,
    ) -> Asset:
        """결제 주기 설정(결제일, 사용 기준일)을 변경한다.

        Args:
            user: 현재 인증된 사용자
            asset_id: 설정할 카드 자산 ID
            payment_day: 결제일 (1~31)
            billing_start_day: 사용 기준일 (1~31, None이면 자동 역산)

        Returns:
            갱신된 Asset 객체

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            BadRequestError: 카드 유형이 아닐 때
            ForbiddenError: 접근 권한이 없을 때
        """
        await self._validate_card_asset(user, asset_id)

        if billing_start_day is None:
            billing_start_day = get_default_billing_start_day(payment_day)

        updated = await self._asset_repo.update(asset_id, {
            "payment_day": payment_day,
            "billing_start_day": billing_start_day,
            "updated_at": datetime.now(timezone.utc),
        })

        logger.info(
            "결제 주기 설정 변경 완료: asset_id=%s, payment_day=%d, billing_start_day=%d",
            asset_id, payment_day, billing_start_day,
        )
        return updated

    async def get_billing_config(
        self, user: User, asset_id: UUID,
    ) -> BillingConfigResponse:
        """결제 주기 설정을 조회한다.

        결제 주기가 미설정된 경우 모든 필드를 null로 반환한다.

        Args:
            user: 현재 인증된 사용자
            asset_id: 조회할 자산 ID

        Returns:
            BillingConfigResponse

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        asset = await self._asset_repo.get_by_id(asset_id)
        if asset is None:
            raise NotFoundError("자산을 찾을 수 없습니다")

        # 소유권 검증 (카드 유형 체크 없이)
        self._check_permission(user, asset)

        if asset.payment_day is None:
            return BillingConfigResponse(
                asset_id=asset_id,
                payment_day=None,
                billing_start_day=None,
                current_cycle=None,
            )

        # 현재 결제 주기 계산
        cycle_info = calc_billing_cycle(
            asset.payment_day, asset.billing_start_day, date.today(),
        )
        current_cycle = BillingCycleResponse(
            start_date=cycle_info.start_date,
            end_date=cycle_info.end_date,
            payment_date=cycle_info.payment_date,
        )

        return BillingConfigResponse(
            asset_id=asset_id,
            payment_day=asset.payment_day,
            billing_start_day=asset.billing_start_day,
            current_cycle=current_cycle,
        )

    # ──────────────────────────────────────────────
    # 결제 주기 조회
    # ──────────────────────────────────────────────

    async def get_billing_cycle(
        self,
        user: User,
        asset_id: UUID,
        reference_date: date | None = None,
    ) -> BillingCycleResponse:
        """현재 또는 특정 기준일의 결제 주기를 조회한다.

        Args:
            user: 현재 인증된 사용자
            asset_id: 카드 자산 ID
            reference_date: 기준 날짜 (None이면 오늘)

        Returns:
            BillingCycleResponse

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            BadRequestError: 카드 유형이 아니거나 결제 주기 미설정 시
            ForbiddenError: 접근 권한이 없을 때
        """
        asset = await self._validate_card_asset(user, asset_id)

        if asset.payment_day is None or asset.billing_start_day is None:
            raise BadRequestError("결제 주기가 설정되지 않았습니다")

        ref = reference_date or date.today()
        cycle_info = calc_billing_cycle(
            asset.payment_day, asset.billing_start_day, ref,
        )

        return BillingCycleResponse(
            start_date=cycle_info.start_date,
            end_date=cycle_info.end_date,
            payment_date=cycle_info.payment_date,
        )

    # ──────────────────────────────────────────────
    # 결제 주기별 거래 조회
    # ──────────────────────────────────────────────

    async def get_billing_transactions(
        self,
        user: User,
        asset_id: UUID,
        reference_date: date | None = None,
    ) -> BillingTransactionsResponse:
        """결제 주기에 해당하는 거래 목록을 조회한다.

        Args:
            user: 현재 인증된 사용자
            asset_id: 카드 자산 ID
            reference_date: 기준 날짜 (None이면 오늘)

        Returns:
            BillingTransactionsResponse

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            BadRequestError: 카드 유형이 아니거나 결제 주기 미설정 시
            ForbiddenError: 접근 권한이 없을 때
        """
        asset = await self._validate_card_asset(user, asset_id)

        if asset.payment_day is None or asset.billing_start_day is None:
            raise BadRequestError("결제 주기가 설정되지 않았습니다")

        ref = reference_date or date.today()
        cycle_info = calc_billing_cycle(
            asset.payment_day, asset.billing_start_day, ref,
        )

        cycle = BillingCycleResponse(
            start_date=cycle_info.start_date,
            end_date=cycle_info.end_date,
            payment_date=cycle_info.payment_date,
        )

        # 거래 조회 (결제 주기 내 전체 거래 — 한 주기는 약 한 달이므로 충분한 limit 설정)
        rows, total_count = await self._transaction_repo.get_list(
            user_id=user.id,
            family_group_id=user.family_group_id,
            filters={
                "asset_id": asset_id,
                "start_date": cycle_info.start_date,
                "end_date": cycle_info.end_date,
                "offset": 0,
                "limit": 100000,
            },
        )

        transactions = [_row_to_transaction_response(row) for row in rows]

        logger.info(
            "결제 주기별 거래 조회 완료: asset_id=%s, 거래 %d건",
            asset_id, total_count,
        )
        return BillingTransactionsResponse(
            cycle=cycle,
            transactions=transactions,
            total_count=total_count,
        )

    # ──────────────────────────────────────────────
    # 청구할인 CRUD
    # ──────────────────────────────────────────────

    async def create_discount(
        self,
        user: User,
        asset_id: UUID,
        data: BillingDiscountCreateRequest,
    ) -> BillingDiscount:
        """청구할인을 등록한다.

        Args:
            user: 현재 인증된 사용자
            asset_id: 카드 자산 ID
            data: 청구할인 생성 요청 데이터

        Returns:
            생성된 BillingDiscount 객체

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            BadRequestError: 카드 유형이 아닐 때
            ForbiddenError: 접근 권한이 없을 때
        """
        await self._validate_card_asset(user, asset_id)

        discount = await self._billing_discount_repo.create({
            "user_id": user.id,
            "asset_id": asset_id,
            "name": data.name,
            "amount": data.amount,
            "cycle_start": data.cycle_start,
            "cycle_end": data.cycle_end,
            "memo": data.memo,
        })

        logger.info("청구할인 등록 완료: discount_id=%s, asset_id=%s", discount.id, asset_id)
        return discount

    async def update_discount(
        self,
        user: User,
        discount_id: UUID,
        data: BillingDiscountUpdateRequest,
    ) -> BillingDiscount:
        """청구할인을 수정한다.

        Args:
            user: 현재 인증된 사용자
            discount_id: 수정할 청구할인 ID
            data: 청구할인 수정 요청 데이터

        Returns:
            갱신된 BillingDiscount 객체

        Raises:
            NotFoundError: 청구할인이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        discount = await self._billing_discount_repo.get_by_id(discount_id)
        if discount is None:
            raise NotFoundError("청구할인을 찾을 수 없습니다")

        if discount.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

        # 명시적으로 전달된 필드만 업데이트 (None으로 설정하여 값 초기화 가능)
        update_data: dict = {}
        for field in ("name", "amount", "memo"):
            if field in data.model_fields_set:
                update_data[field] = getattr(data, field)

        update_data["updated_at"] = datetime.now(timezone.utc)

        updated = await self._billing_discount_repo.update(discount_id, update_data)
        logger.info("청구할인 수정 완료: discount_id=%s", discount_id)
        return updated

    async def delete_discount(self, user: User, discount_id: UUID) -> None:
        """청구할인을 삭제한다.

        Args:
            user: 현재 인증된 사용자
            discount_id: 삭제할 청구할인 ID

        Raises:
            NotFoundError: 청구할인이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        discount = await self._billing_discount_repo.get_by_id(discount_id)
        if discount is None:
            raise NotFoundError("청구할인을 찾을 수 없습니다")

        if discount.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

        await self._billing_discount_repo.delete(discount_id)
        logger.info("청구할인 삭제 완료: discount_id=%s", discount_id)

    # ──────────────────────────────────────────────
    # 결제 예정 금액 조회
    # ──────────────────────────────────────────────

    async def get_billing_summary(
        self,
        user: User,
        asset_id: UUID,
        reference_date: date | None = None,
    ) -> BillingSummaryResponse:
        """결제 예정 금액 요약을 조회한다.

        총 사용 금액, 청구할인 합계, 결제 예정 금액(= max(0, 사용 - 할인)),
        다음 결제 예정일을 계산하여 반환한다.

        Args:
            user: 현재 인증된 사용자
            asset_id: 카드 자산 ID
            reference_date: 기준 날짜 (None이면 오늘)

        Returns:
            BillingSummaryResponse

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            BadRequestError: 카드 유형이 아니거나 결제 주기 미설정 시
            ForbiddenError: 접근 권한이 없을 때
        """
        asset = await self._validate_card_asset(user, asset_id)

        if asset.payment_day is None or asset.billing_start_day is None:
            raise BadRequestError("결제 주기가 설정되지 않았습니다")

        ref = reference_date or date.today()
        cycle_info = calc_billing_cycle(
            asset.payment_day, asset.billing_start_day, ref,
        )

        cycle = BillingCycleResponse(
            start_date=cycle_info.start_date,
            end_date=cycle_info.end_date,
            payment_date=cycle_info.payment_date,
        )

        # 총 사용 금액: DB에서 직접 SUM 집계
        total_usage = await self._transaction_repo.sum_actual_amount(
            user_id=user.id,
            asset_id=asset_id,
            start_date=cycle_info.start_date,
            end_date=cycle_info.end_date,
        )

        # 청구할인 합계
        total_discount = await self._billing_discount_repo.sum_by_asset_and_cycle(
            asset_id, cycle_info.start_date, cycle_info.end_date,
        )

        estimated_payment = max(0, total_usage - total_discount)

        next_payment_date = get_next_payment_date(asset.payment_day, ref)

        logger.info(
            "결제 예정 금액 조회 완료: asset_id=%s, 사용=%d, 할인=%d, 예정=%d",
            asset_id, total_usage, total_discount, estimated_payment,
        )
        return BillingSummaryResponse(
            cycle=cycle,
            total_usage=total_usage,
            total_discount=total_discount,
            estimated_payment=estimated_payment,
            next_payment_date=next_payment_date,
        )
