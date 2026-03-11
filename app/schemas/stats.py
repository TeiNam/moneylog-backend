"""
통계(Stats) 관련 Pydantic 응답 스키마.

주간/월간/연간 통계 API에서 사용하는 응답 모델을 정의한다.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


# ──────────────────────────────────────────────
# 주간 통계
# ──────────────────────────────────────────────


class DailyExpense(BaseModel):
    """일별 지출 데이터."""

    date: date
    amount: int


class AreaBreakdown(BaseModel):
    """영역별 비중 데이터."""

    area: str
    amount: int
    ratio: float


class WeeklyStatsResponse(BaseModel):
    """주간 통계 응답."""

    start_date: date
    end_date: date
    total_expense: int
    daily_average: int
    no_spend_days: int
    daily_expenses: list[DailyExpense]
    area_breakdown: list[AreaBreakdown]


# ──────────────────────────────────────────────
# 월간 통계
# ──────────────────────────────────────────────


class CategoryBreakdown(BaseModel):
    """카테고리별 비중 데이터."""

    category: str
    amount: int
    ratio: float
    prev_month_change_rate: float | None = None


class BudgetVsActual(BaseModel):
    """예산 대비 실적 데이터."""

    category: str
    budget_amount: int
    actual_amount: int
    remaining: int
    usage_rate: float


class AssetBreakdown(BaseModel):
    """결제수단별 비중 데이터."""

    asset_id: UUID | None
    amount: int
    ratio: float


class MonthlyStatsResponse(BaseModel):
    """월간 통계 응답."""

    year: int
    month: int
    total_income: int
    total_expense: int
    balance: int
    category_breakdown: list[CategoryBreakdown]
    budget_vs_actual: list[BudgetVsActual]
    prev_month_change_rate: float | None
    asset_breakdown: list[AssetBreakdown]


# ──────────────────────────────────────────────
# 연간 통계
# ──────────────────────────────────────────────


class MonthlyTrend(BaseModel):
    """월별 수입/지출 추이 데이터."""

    month: int
    income: int
    expense: int


class CeremonySummary(BaseModel):
    """경조사 연간 요약."""

    sent_total: int
    received_total: int


class SubscriptionSummaryStats(BaseModel):
    """구독 연간 요약."""

    total_expense: int
    active_count: int
    cancelled_count: int


class YearlyStatsResponse(BaseModel):
    """연간 통계 응답."""

    year: int
    monthly_trends: list[MonthlyTrend]
    total_income: int
    total_expense: int
    savings: int
    savings_rate: float
    top_categories: list[CategoryBreakdown]
    ceremony_summary: CeremonySummary
    subscription_summary: SubscriptionSummaryStats
