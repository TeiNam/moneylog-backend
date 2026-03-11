"""
통계(Stats) 비즈니스 로직 서비스.

주간/월간/연간 통계 집계 및 순수 계산 함수를 제공한다.
"""

import calendar
import logging
from datetime import date, timedelta
from uuid import UUID

from app.models.user import User
from app.repositories.budget_repository import BudgetRepository
from app.repositories.stats_repository import StatsRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.stats import (
    AreaBreakdown,
    AssetBreakdown,
    BudgetVsActual,
    CategoryBreakdown,
    CeremonySummary,
    DailyExpense,
    MonthlyStatsResponse,
    MonthlyTrend,
    SubscriptionSummaryStats,
    WeeklyStatsResponse,
    YearlyStatsResponse,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 순수 함수 (DB 없이 독립 테스트 가능)
# ══════════════════════════════════════════════


def calculate_change_rate(current: int, previous: int) -> float | None:
    """전월 대비 증감률을 계산한다. 전월이 0이면 None 반환."""
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def calculate_savings_rate(income: int, expense: int) -> float:
    """저축률을 계산한다. 수입이 0이면 0.0 반환."""
    if income == 0:
        return 0.0
    return round((income - expense) / income * 100, 1)


def get_week_range(target_date: date) -> tuple[date, date]:
    """해당 날짜가 속한 주의 시작일(월요일)과 종료일(일요일)을 반환한다."""
    weekday = target_date.weekday()  # 0=월, 6=일
    start = target_date - timedelta(days=weekday)
    end = start + timedelta(days=6)
    return start, end


class StatsService:
    """주간/월간/연간 통계 집계 서비스."""

    def __init__(
        self,
        stats_repo: StatsRepository,
        budget_repo: BudgetRepository,
        subscription_repo: SubscriptionRepository | None = None,
    ) -> None:
        self._stats_repo = stats_repo
        self._budget_repo = budget_repo
        self._subscription_repo = subscription_repo

    # ──────────────────────────────────────────────
    # 주간 통계
    # ──────────────────────────────────────────────

    async def get_weekly_stats(self, user: User, target_date: date) -> WeeklyStatsResponse:
        """해당 날짜가 속한 주(월~일)의 통계를 반환한다."""
        start_date, end_date = get_week_range(target_date)

        # 주간 지출 합계
        total_expense = await self._stats_repo.get_expense_sum_by_date_range(
            user.id, start_date, end_date
        )

        # 일평균 (정수 내림)
        daily_average = total_expense // 7

        # 일별 지출 합계
        daily_sums = await self._stats_repo.get_daily_expense_sums(
            user.id, start_date, end_date
        )
        daily_map = {item["date"]: item["amount"] for item in daily_sums}

        # 7일간 일별 데이터 생성 (지출 없는 날은 0)
        daily_expenses = []
        no_spend_days = 0
        for i in range(7):
            d = start_date + timedelta(days=i)
            amount = daily_map.get(d, 0)
            daily_expenses.append(DailyExpense(date=d, amount=amount))
            if amount == 0:
                no_spend_days += 1

        # 영역별 비중
        area_data = await self._stats_repo.get_expense_by_area(
            user.id, start_date, end_date
        )
        area_breakdown = []
        for item in area_data:
            ratio = round(item["amount"] / total_expense * 100, 1) if total_expense > 0 else 0.0
            area_breakdown.append(
                AreaBreakdown(area=item["area"], amount=item["amount"], ratio=ratio)
            )

        return WeeklyStatsResponse(
            start_date=start_date,
            end_date=end_date,
            total_expense=total_expense,
            daily_average=daily_average,
            no_spend_days=no_spend_days,
            daily_expenses=daily_expenses,
            area_breakdown=area_breakdown,
        )

    # ──────────────────────────────────────────────
    # 월간 통계
    # ──────────────────────────────────────────────

    async def get_monthly_stats(self, user: User, year: int, month: int) -> MonthlyStatsResponse:
        """해당 연월의 월간 통계를 반환한다."""
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # 수입/지출 합계
        total_income = await self._stats_repo.get_income_sum_by_date_range(
            user.id, start_date, end_date
        )
        total_expense = await self._stats_repo.get_expense_sum_by_date_range(
            user.id, start_date, end_date
        )
        balance = total_income - total_expense

        # 카테고리별 지출 비중
        category_data = await self._stats_repo.get_expense_by_category(
            user.id, start_date, end_date
        )

        # 전월 카테고리별 지출 (증감률 계산용)
        if month == 1:
            prev_start = date(year - 1, 12, 1)
            prev_end = date(year - 1, 12, 31)
        else:
            prev_start = date(year, month - 1, 1)
            prev_last_day = calendar.monthrange(year, month - 1)[1]
            prev_end = date(year, month - 1, prev_last_day)

        prev_category_data = await self._stats_repo.get_expense_by_category(
            user.id, prev_start, prev_end
        )
        prev_category_map = {item["category"]: item["amount"] for item in prev_category_data}

        category_breakdown = []
        for item in category_data:
            ratio = round(item["amount"] / total_expense * 100, 1) if total_expense > 0 else 0.0
            prev_amount = prev_category_map.get(item["category"], 0)
            change_rate = calculate_change_rate(item["amount"], prev_amount)
            category_breakdown.append(
                CategoryBreakdown(
                    category=item["category"],
                    amount=item["amount"],
                    ratio=ratio,
                    prev_month_change_rate=change_rate,
                )
            )

        # 예산 대비 실적
        budgets = await self._budget_repo.get_list_by_user_month(user.id, year, month)
        expense_map = {item["category"]: item["amount"] for item in category_data}
        budget_vs_actual = []
        for budget in budgets:
            actual = expense_map.get(budget.category, 0)
            remaining = budget.budget_amount - actual
            usage_rate = round(actual / budget.budget_amount * 100, 1) if budget.budget_amount > 0 else 0.0
            budget_vs_actual.append(
                BudgetVsActual(
                    category=budget.category,
                    budget_amount=budget.budget_amount,
                    actual_amount=actual,
                    remaining=remaining,
                    usage_rate=usage_rate,
                )
            )

        # 전월 대비 증감률 (총지출 기준)
        prev_total_expense = await self._stats_repo.get_expense_sum_by_date_range(
            user.id, prev_start, prev_end
        )
        prev_month_change_rate = calculate_change_rate(total_expense, prev_total_expense)

        # 결제수단별 지출 비중
        asset_data = await self._stats_repo.get_expense_by_asset(
            user.id, start_date, end_date
        )
        asset_breakdown = []
        for item in asset_data:
            ratio = round(item["amount"] / total_expense * 100, 1) if total_expense > 0 else 0.0
            asset_breakdown.append(
                AssetBreakdown(asset_id=item["asset_id"], amount=item["amount"], ratio=ratio)
            )

        return MonthlyStatsResponse(
            year=year,
            month=month,
            total_income=total_income,
            total_expense=total_expense,
            balance=balance,
            category_breakdown=category_breakdown,
            budget_vs_actual=budget_vs_actual,
            prev_month_change_rate=prev_month_change_rate,
            asset_breakdown=asset_breakdown,
        )

    # ──────────────────────────────────────────────
    # 연간 통계
    # ──────────────────────────────────────────────

    async def get_yearly_stats(self, user: User, year: int) -> YearlyStatsResponse:
        """해당 연도의 연간 통계를 반환한다."""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        # 월별 수입/지출 추이
        monthly_data = await self._stats_repo.get_monthly_income_expense(user.id, year)
        monthly_map = {item["month"]: item for item in monthly_data}

        monthly_trends = []
        for m in range(1, 13):
            data = monthly_map.get(m, {"income": 0, "expense": 0})
            monthly_trends.append(
                MonthlyTrend(month=m, income=data["income"], expense=data["expense"])
            )

        # 연간 총수입/총지출
        total_income = sum(t.income for t in monthly_trends)
        total_expense = sum(t.expense for t in monthly_trends)
        savings = total_income - total_expense
        savings_rate = calculate_savings_rate(total_income, total_expense)

        # TOP 카테고리 (지출 내림차순)
        category_data = await self._stats_repo.get_expense_by_category(
            user.id, start_date, end_date
        )
        category_data.sort(key=lambda x: x["amount"], reverse=True)
        top_categories = []
        for item in category_data:
            ratio = round(item["amount"] / total_expense * 100, 1) if total_expense > 0 else 0.0
            top_categories.append(
                CategoryBreakdown(category=item["category"], amount=item["amount"], ratio=ratio)
            )

        # 경조사 연간 요약
        ceremony_data = await self._stats_repo.get_ceremony_summary(user.id, year)
        ceremony_summary = CeremonySummary(
            sent_total=ceremony_data["sent_total"],
            received_total=ceremony_data["received_total"],
        )

        # 구독 연간 요약
        subscription_expense = await self._stats_repo.get_subscription_expense_sum(user.id, year)
        active_count = 0
        cancelled_count = 0
        if self._subscription_repo:
            active_count = await self._subscription_repo.count_by_user_and_status(user.id, "ACTIVE")
            cancelled_count = await self._subscription_repo.count_by_user_and_status(user.id, "CANCELLED")

        subscription_summary = SubscriptionSummaryStats(
            total_expense=subscription_expense,
            active_count=active_count,
            cancelled_count=cancelled_count,
        )

        return YearlyStatsResponse(
            year=year,
            monthly_trends=monthly_trends,
            total_income=total_income,
            total_expense=total_expense,
            savings=savings,
            savings_rate=savings_rate,
            top_categories=top_categories,
            ceremony_summary=ceremony_summary,
            subscription_summary=subscription_summary,
        )
