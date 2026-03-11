"""
통계(Stats) 집계 레포지토리.

Transaction 및 CeremonyEvent 데이터를 집계하여 통계 데이터를 제공한다.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.

비밀 거래(is_private) 필터링 정책:
- 가족 통계: is_private == False 필터를 적용하여 비밀 거래를 제외한다.
- 개인 통계: 본인 거래이므로 비밀 거래를 포함한다 (is_private 필터 미적용).
"""

import calendar
import logging
from datetime import date
from uuid import UUID

from sqlalchemy import and_, case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import CeremonyEvent, Transaction

logger = logging.getLogger(__name__)


class StatsRepository:
    """통계 집계를 위한 Transaction 데이터 조회 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_expense_sum_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> int:
        """기간 내 EXPENSE actual_amount 합계를 반환한다.

        개인 통계: 본인 거래는 비밀 거래 포함 (의도된 동작)
        """
        stmt = select(func.coalesce(func.sum(Transaction.actual_amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.type == "EXPENSE",
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_income_sum_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> int:
        """기간 내 INCOME actual_amount 합계를 반환한다.

        개인 통계: 본인 거래는 비밀 거래 포함 (의도된 동작)
        """
        stmt = select(func.coalesce(func.sum(Transaction.actual_amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.type == "INCOME",
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_daily_expense_sums(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> list[dict]:
        """기간 내 일별 EXPENSE actual_amount 합계를 반환한다.

        개인 통계: 본인 거래는 비밀 거래 포함 (의도된 동작)
        """
        stmt = (
            select(
                Transaction.date,
                func.sum(Transaction.actual_amount).label("amount"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            )
            .group_by(Transaction.date)
        )
        result = await self._session.execute(stmt)
        return [{"date": row.date, "amount": row.amount} for row in result.all()]

    async def get_expense_by_area(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> list[dict]:
        """기간 내 영역별(area) EXPENSE actual_amount 합계를 반환한다.

        개인 통계: 본인 거래는 비밀 거래 포함 (의도된 동작)
        """
        stmt = (
            select(
                Transaction.area,
                func.sum(Transaction.actual_amount).label("amount"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            )
            .group_by(Transaction.area)
        )
        result = await self._session.execute(stmt)
        return [{"area": row.area, "amount": row.amount} for row in result.all()]

    async def get_expense_by_category(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> list[dict]:
        """기간 내 카테고리별(major_category) EXPENSE actual_amount 합계를 반환한다.

        개인 통계: 본인 거래는 비밀 거래 포함 (의도된 동작)
        """
        stmt = (
            select(
                Transaction.major_category.label("category"),
                func.sum(Transaction.actual_amount).label("amount"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            )
            .group_by(Transaction.major_category)
        )
        result = await self._session.execute(stmt)
        return [{"category": row.category, "amount": row.amount} for row in result.all()]

    async def get_expense_by_asset(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> list[dict]:
        """기간 내 결제수단별(asset_id) EXPENSE actual_amount 합계를 반환한다.

        개인 통계: 본인 거래는 비밀 거래 포함 (의도된 동작)
        """
        stmt = (
            select(
                Transaction.asset_id,
                func.sum(Transaction.actual_amount).label("amount"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            )
            .group_by(Transaction.asset_id)
        )
        result = await self._session.execute(stmt)
        return [{"asset_id": row.asset_id, "amount": row.amount} for row in result.all()]

    async def get_monthly_income_expense(
        self, user_id: UUID, year: int
    ) -> list[dict]:
        """연도 내 월별 INCOME/EXPENSE actual_amount 합계를 반환한다.

        개인 통계: 본인 거래는 비밀 거래 포함 (의도된 동작)
        """
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        stmt = (
            select(
                extract("month", Transaction.date).label("month"),
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.type == "INCOME", Transaction.actual_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("income"),
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.type == "EXPENSE", Transaction.actual_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("expense"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            )
            .group_by(extract("month", Transaction.date))
        )
        result = await self._session.execute(stmt)
        return [
            {"month": int(row.month), "income": row.income, "expense": row.expense}
            for row in result.all()
        ]

    async def get_ceremony_summary(
        self, user_id: UUID, year: int
    ) -> dict:
        """연도 내 경조사 SENT/RECEIVED 금액 합계를 반환한다."""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (CeremonyEvent.direction == "SENT", Transaction.actual_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("sent_total"),
                func.coalesce(
                    func.sum(
                        case(
                            (CeremonyEvent.direction == "RECEIVED", Transaction.actual_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("received_total"),
            )
            .select_from(Transaction)
            .join(CeremonyEvent, CeremonyEvent.transaction_id == Transaction.id)
            .where(
                Transaction.user_id == user_id,
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            )
        )
        result = await self._session.execute(stmt)
        row = result.one()
        return {"sent_total": row.sent_total, "received_total": row.received_total}

    async def get_subscription_expense_sum(
        self, user_id: UUID, year: int
    ) -> int:
        """연도 내 area=SUBSCRIPTION인 EXPENSE actual_amount 합계를 반환한다."""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        stmt = select(func.coalesce(func.sum(Transaction.actual_amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.type == "EXPENSE",
            Transaction.area == "SUBSCRIPTION",
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_family_member_expenses(
        self, family_group_id: UUID, year: int, month: int
    ) -> list[dict]:
        """가족 그룹 내 구성원별 월간 EXPENSE actual_amount 합계를 반환한다.

        가족 통계: 비밀 거래 제외 (is_private == False 필터 적용)
        """

        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        stmt = (
            select(
                Transaction.user_id,
                func.sum(Transaction.actual_amount).label("amount"),
            )
            .where(
                Transaction.family_group_id == family_group_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
                Transaction.is_private == False,  # 비밀 거래 제외 (Phase 6)
            )
            .group_by(Transaction.user_id)
        )
        result = await self._session.execute(stmt)
        return [{"user_id": row.user_id, "amount": row.amount} for row in result.all()]

    async def get_family_member_expenses_by_asset(
        self, family_group_id: UUID, year: int, month: int
    ) -> list[dict]:
        """가족 그룹 내 구성원별 결제수단별 월간 EXPENSE actual_amount 합계를 반환한다.

        가족 통계: 비밀 거래 제외 (is_private == False 필터 적용)
        """

        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        stmt = (
            select(
                Transaction.user_id,
                Transaction.asset_id,
                func.sum(Transaction.actual_amount).label("amount"),
            )
            .where(
                Transaction.family_group_id == family_group_id,
                Transaction.type == "EXPENSE",
                Transaction.date >= start_date,
                Transaction.date <= end_date,
                Transaction.is_private == False,  # 비밀 거래 제외 (Phase 6)
            )
            .group_by(Transaction.user_id, Transaction.asset_id)
        )
        result = await self._session.execute(stmt)
        return [
            {"user_id": row.user_id, "asset_id": row.asset_id, "amount": row.amount}
            for row in result.all()
        ]
