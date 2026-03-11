"""
AI 분석 서비스.

월간 지출 분석 리포트 생성 및 예산 초과 절약 제안 기능을 제공한다.
기존 StatsRepository, BudgetRepository를 활용하여 데이터를 수집하고,
BedrockClient를 통해 AI 기반 분석 코멘트와 절약 팁을 생성한다.
"""

import calendar
import logging
from datetime import date
from uuid import UUID

from app.core.exceptions import BadRequestError
from app.repositories.budget_repository import BudgetRepository
from app.repositories.stats_repository import StatsRepository
from app.schemas.ai_analysis import (
    CategoryTrend,
    MonthlyAnalysisResponse,
    OverBudgetCategory,
    SavingsTipsResponse,
)
from app.services.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """AI 기반 월간 지출 분석 및 절약 제안 서비스."""

    def __init__(
        self,
        stats_repo: StatsRepository,
        budget_repo: BudgetRepository,
        bedrock_client: BedrockClient,
    ) -> None:
        self._stats_repo = stats_repo
        self._budget_repo = budget_repo
        self._bedrock_client = bedrock_client

    async def get_monthly_analysis(
        self, user_id: UUID, year: int, month: int
    ) -> MonthlyAnalysisResponse:
        """월간 지출 분석 리포트를 생성한다.

        카테고리별 지출 합계, 전월 대비 증감, 예산 대비 실적 데이터를 수집하고
        Bedrock Claude에 분석을 요청하여 요약 코멘트와 카테고리별 트렌드를 반환한다.

        Raises:
            BadRequestError: 해당 연월에 거래 데이터가 없을 때
            BedrockError: Bedrock API 호출 실패 시
        """
        # 현재 월 날짜 범위 계산
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # 전월 날짜 범위 계산
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1
        prev_start = date(prev_year, prev_month, 1)
        prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
        prev_end = date(prev_year, prev_month, prev_last_day)

        # 카테고리별 지출 조회
        current_expenses = await self._stats_repo.get_expense_by_category(
            user_id, start_date, end_date
        )

        # 거래 데이터 없음 검증
        if not current_expenses:
            raise BadRequestError("해당 기간의 거래 데이터가 없습니다")

        # 전월 카테고리별 지출 조회
        previous_expenses = await self._stats_repo.get_expense_by_category(
            user_id, prev_start, prev_end
        )

        # 예산 목록 조회
        budgets = await self._budget_repo.get_list_by_user_month(
            user_id, year, month
        )

        # 전월 데이터를 딕셔너리로 변환
        prev_map = {item["category"]: item["amount"] for item in previous_expenses}

        # 예산 데이터를 딕셔너리로 변환
        budget_map = {b.category: b.budget_amount for b in budgets}

        # 카테고리별 트렌드 구성
        category_trends: list[CategoryTrend] = []
        for item in current_expenses:
            cat = item["category"]
            current_amount = item["amount"]
            previous_amount = prev_map.get(cat, 0)

            # 증감률 계산
            change_rate = None
            if previous_amount > 0:
                change_rate = round(
                    (current_amount - previous_amount) / previous_amount * 100, 1
                )

            # 증감 방향 결정
            if current_amount > previous_amount:
                direction = "increase"
            elif current_amount < previous_amount:
                direction = "decrease"
            else:
                direction = "unchanged"

            category_trends.append(
                CategoryTrend(
                    category=cat,
                    current_amount=current_amount,
                    previous_amount=previous_amount,
                    change_rate=change_rate,
                    direction=direction,
                )
            )

        # 분석 데이터 문자열 구성
        analysis_lines = [f"{year}년 {month}월 지출 분석 데이터:"]
        for trend in category_trends:
            line = f"- {trend.category}: {trend.current_amount:,}원"
            if trend.previous_amount > 0:
                line += f" (전월 {trend.previous_amount:,}원, {trend.direction}"
                if trend.change_rate is not None:
                    line += f" {trend.change_rate}%"
                line += ")"
            budget_amt = budget_map.get(trend.category)
            if budget_amt is not None:
                line += f" [예산 {budget_amt:,}원]"
            analysis_lines.append(line)

        analysis_data = "\n".join(analysis_lines)

        # Bedrock에 분석 요청
        system_prompt = (
            "당신은 가계부 지출 분석 전문가입니다. "
            "사용자의 월간 지출 데이터를 분석하여 간결하고 유용한 요약 코멘트를 작성해주세요. "
            "한국어로 답변하세요."
        )
        messages = [
            {
                "role": "user",
                "content": [{"text": analysis_data}],
            }
        ]

        summary = await self._bedrock_client.converse(
            system_prompt=system_prompt,
            messages=messages,
        )

        return MonthlyAnalysisResponse(
            year=year,
            month=month,
            summary=summary,
            category_trends=category_trends,
        )

    async def get_savings_tips(
        self, user_id: UUID, year: int, month: int
    ) -> SavingsTipsResponse:
        """예산 초과 카테고리에 대한 절약 제안을 생성한다.

        예산 대비 실적 데이터를 조회하고, 초과 카테고리를 식별하여
        Bedrock Claude에 절약 팁 생성을 요청한다.
        예산 미설정 시 설정 권유 메시지, 모든 카테고리 예산 이내 시 긍정적 피드백을 반환한다.

        Raises:
            BedrockError: Bedrock API 호출 실패 시
        """
        # 예산 목록 조회
        budgets = await self._budget_repo.get_list_by_user_month(
            user_id, year, month
        )

        # 예산 미설정 시 설정 권유 메시지 반환
        if not budgets:
            return SavingsTipsResponse(
                year=year,
                month=month,
                over_budget_categories=[],
                tips="",
                message="예산을 설정하면 맞춤형 절약 제안을 받을 수 있습니다",
            )

        # 현재 월 날짜 범위 계산
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # 카테고리별 지출 조회
        expenses = await self._stats_repo.get_expense_by_category(
            user_id, start_date, end_date
        )
        expense_map = {item["category"]: item["amount"] for item in expenses}

        # 초과 카테고리 식별
        over_budget_categories: list[OverBudgetCategory] = []
        for budget in budgets:
            actual = expense_map.get(budget.category, 0)
            if actual > budget.budget_amount:
                over_budget_categories.append(
                    OverBudgetCategory(
                        category=budget.category,
                        budget_amount=budget.budget_amount,
                        actual_amount=actual,
                        over_amount=actual - budget.budget_amount,
                    )
                )

        # 모든 카테고리 예산 이내 시 긍정적 피드백 반환
        if not over_budget_categories:
            return SavingsTipsResponse(
                year=year,
                month=month,
                over_budget_categories=[],
                tips="",
                message="모든 카테고리가 예산 이내입니다. 잘 관리하고 계세요!",
            )

        # 초과 데이터 문자열 구성
        over_lines = [f"{year}년 {month}월 예산 초과 카테고리:"]
        for obc in over_budget_categories:
            over_lines.append(
                f"- {obc.category}: 예산 {obc.budget_amount:,}원, "
                f"실제 {obc.actual_amount:,}원 (초과 {obc.over_amount:,}원)"
            )
        over_data = "\n".join(over_lines)

        # Bedrock에 절약 팁 생성 요청
        system_prompt = (
            "당신은 가계부 절약 전문가입니다. "
            "예산을 초과한 카테고리에 대해 구체적인 금액 목표와 실행 가능한 절약 팁을 제안해주세요. "
            "한국어로 답변하세요."
        )
        messages = [
            {
                "role": "user",
                "content": [{"text": over_data}],
            }
        ]

        tips = await self._bedrock_client.converse(
            system_prompt=system_prompt,
            messages=messages,
        )

        return SavingsTipsResponse(
            year=year,
            month=month,
            over_budget_categories=over_budget_categories,
            tips=tips,
            message=None,
        )
