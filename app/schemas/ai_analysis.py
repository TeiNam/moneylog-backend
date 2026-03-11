"""AI 분석 관련 Pydantic 스키마."""

from pydantic import BaseModel


class CategoryTrend(BaseModel):
    """카테고리별 지출 트렌드."""
    category: str
    current_amount: int
    previous_amount: int
    change_rate: float | None
    direction: str  # "increase", "decrease", "unchanged"


class MonthlyAnalysisResponse(BaseModel):
    """월간 지출 분석 응답."""
    year: int
    month: int
    summary: str
    category_trends: list[CategoryTrend]


class OverBudgetCategory(BaseModel):
    """예산 초과 카테고리."""
    category: str
    budget_amount: int
    actual_amount: int
    over_amount: int


class SavingsTipsResponse(BaseModel):
    """절약 제안 응답."""
    year: int
    month: int
    over_budget_categories: list[OverBudgetCategory]
    tips: str
    message: str | None = None
