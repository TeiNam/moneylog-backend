"""
AIAnalysisService 단위 테스트 및 속성 기반 테스트.

월간 분석, 절약 제안, 데이터 없음/예산 없음 분기, 에러 케이스를 검증한다.
StatsRepository, BudgetRepository, BedrockClient는 Mock으로 대체한다.
"""

import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.exceptions import BadRequestError
from app.schemas.ai_analysis import (
    MonthlyAnalysisResponse,
    SavingsTipsResponse,
)
from app.services.ai_analysis_service import AIAnalysisService
from app.services.bedrock_client import BedrockError


# ══════════════════════════════════════════════
# Mock 클래스
# ══════════════════════════════════════════════


class MockStatsRepository:
    """테스트용 StatsRepository 모킹."""

    def __init__(self, category_expenses=None):
        self._category_expenses = category_expenses or []

    async def get_expense_by_category(self, user_id, start_date, end_date):
        return self._category_expenses


class MockBudgetRepository:
    """테스트용 BudgetRepository 모킹."""

    def __init__(self, budgets=None):
        self._budgets = budgets or []

    async def get_list_by_user_month(self, user_id, year, month):
        return self._budgets


class MockBedrockClient:
    """테스트용 BedrockClient 모킹."""

    def __init__(self, response="", should_fail=False):
        self.response = response
        self.should_fail = should_fail
        self.call_count = 0

    async def converse(self, system_prompt, messages, max_tokens=4096):
        self.call_count += 1
        if self.should_fail:
            raise BedrockError("AI 서비스 호출에 실패했습니다")
        return self.response


class MockBudget:
    """테스트용 Budget 객체."""

    def __init__(self, category, budget_amount):
        self.category = category
        self.budget_amount = budget_amount


# ══════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════


def _build_service(
    category_expenses=None,
    prev_expenses=None,
    budgets=None,
    bedrock_response="",
    bedrock_should_fail=False,
) -> tuple[AIAnalysisService, MockBedrockClient]:
    """테스트용 AIAnalysisService 인스턴스를 생성한다.

    prev_expenses가 제공되면 호출 순서에 따라 다른 결과를 반환하는
    StatsRepository를 생성한다.
    """
    if prev_expenses is not None:
        # 첫 번째 호출: 현재 월, 두 번째 호출: 전월
        stats_repo = MockStatsRepositoryWithPrev(
            current=category_expenses or [],
            previous=prev_expenses,
        )
    else:
        stats_repo = MockStatsRepository(category_expenses)

    budget_repo = MockBudgetRepository(budgets)
    bedrock_client = MockBedrockClient(
        response=bedrock_response,
        should_fail=bedrock_should_fail,
    )

    service = AIAnalysisService(
        stats_repo=stats_repo,
        budget_repo=budget_repo,
        bedrock_client=bedrock_client,
    )
    return service, bedrock_client


class MockStatsRepositoryWithPrev:
    """현재 월과 전월 데이터를 구분하여 반환하는 StatsRepository 모킹."""

    def __init__(self, current=None, previous=None):
        self._current = current or []
        self._previous = previous or []
        self._call_count = 0

    async def get_expense_by_category(self, user_id, start_date, end_date):
        self._call_count += 1
        if self._call_count == 1:
            return self._current
        return self._previous


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_monthly_analysis_normal():
    """월간 분석 정상 동작 검증 (BedrockClient 모킹)."""
    user_id = uuid.uuid4()
    current = [
        {"category": "식비", "amount": 300000},
        {"category": "교통", "amount": 100000},
    ]
    prev = [
        {"category": "식비", "amount": 250000},
        {"category": "교통", "amount": 120000},
    ]
    budgets = [
        MockBudget("식비", 350000),
        MockBudget("교통", 150000),
    ]

    service, mock_bedrock = _build_service(
        category_expenses=current,
        prev_expenses=prev,
        budgets=budgets,
        bedrock_response="이번 달 식비가 전월 대비 20% 증가했습니다.",
    )

    result = await service.get_monthly_analysis(user_id, 2025, 6)

    assert isinstance(result, MonthlyAnalysisResponse)
    assert result.year == 2025
    assert result.month == 6
    assert result.summary == "이번 달 식비가 전월 대비 20% 증가했습니다."
    assert len(result.category_trends) == 2
    assert mock_bedrock.call_count == 1

    # 식비 트렌드 검증
    food_trend = next(t for t in result.category_trends if t.category == "식비")
    assert food_trend.current_amount == 300000
    assert food_trend.previous_amount == 250000
    assert food_trend.direction == "increase"
    assert food_trend.change_rate == 20.0

    # 교통 트렌드 검증
    transport_trend = next(t for t in result.category_trends if t.category == "교통")
    assert transport_trend.current_amount == 100000
    assert transport_trend.previous_amount == 120000
    assert transport_trend.direction == "decrease"


@pytest.mark.asyncio
async def test_monthly_analysis_no_data():
    """거래 데이터 없음 시 BadRequestError 검증."""
    user_id = uuid.uuid4()
    service, _ = _build_service(category_expenses=[])

    with pytest.raises(BadRequestError, match="해당 기간의 거래 데이터가 없습니다"):
        await service.get_monthly_analysis(user_id, 2025, 6)


@pytest.mark.asyncio
async def test_savings_tips_over_budget():
    """절약 제안 정상 동작 검증 (초과 카테고리 있는 경우)."""
    user_id = uuid.uuid4()
    budgets = [
        MockBudget("식비", 200000),
        MockBudget("교통", 100000),
    ]
    expenses = [
        {"category": "식비", "amount": 300000},
        {"category": "교통", "amount": 80000},
    ]

    stats_repo = MockStatsRepository(expenses)
    budget_repo = MockBudgetRepository(budgets)
    bedrock_client = MockBedrockClient(response="식비를 줄이기 위해 도시락을 준비해보세요.")

    service = AIAnalysisService(
        stats_repo=stats_repo,
        budget_repo=budget_repo,
        bedrock_client=bedrock_client,
    )

    result = await service.get_savings_tips(user_id, 2025, 6)

    assert isinstance(result, SavingsTipsResponse)
    assert result.year == 2025
    assert result.month == 6
    assert len(result.over_budget_categories) == 1
    assert result.over_budget_categories[0].category == "식비"
    assert result.over_budget_categories[0].over_amount == 100000
    assert result.tips == "식비를 줄이기 위해 도시락을 준비해보세요."
    assert result.message is None
    assert bedrock_client.call_count == 1


@pytest.mark.asyncio
async def test_savings_tips_no_budget():
    """예산 미설정 시 설정 권유 메시지 반환 검증."""
    user_id = uuid.uuid4()
    service, mock_bedrock = _build_service(budgets=[])

    result = await service.get_savings_tips(user_id, 2025, 6)

    assert isinstance(result, SavingsTipsResponse)
    assert result.message == "예산을 설정하면 맞춤형 절약 제안을 받을 수 있습니다"
    assert result.over_budget_categories == []
    assert result.tips == ""
    # Bedrock 호출 없음
    assert mock_bedrock.call_count == 0


@pytest.mark.asyncio
async def test_savings_tips_all_within_budget():
    """모든 카테고리 예산 이내 시 긍정적 피드백 반환 검증."""
    user_id = uuid.uuid4()
    budgets = [
        MockBudget("식비", 500000),
        MockBudget("교통", 200000),
    ]
    expenses = [
        {"category": "식비", "amount": 300000},
        {"category": "교통", "amount": 100000},
    ]

    stats_repo = MockStatsRepository(expenses)
    budget_repo = MockBudgetRepository(budgets)
    bedrock_client = MockBedrockClient()

    service = AIAnalysisService(
        stats_repo=stats_repo,
        budget_repo=budget_repo,
        bedrock_client=bedrock_client,
    )

    result = await service.get_savings_tips(user_id, 2025, 6)

    assert isinstance(result, SavingsTipsResponse)
    assert result.message == "모든 카테고리가 예산 이내입니다. 잘 관리하고 계세요!"
    assert result.over_budget_categories == []
    assert result.tips == ""
    # Bedrock 호출 없음
    assert bedrock_client.call_count == 0


@pytest.mark.asyncio
async def test_monthly_analysis_bedrock_error():
    """Bedrock API 실패 시 에러 처리 검증."""
    user_id = uuid.uuid4()
    current = [{"category": "식비", "amount": 300000}]

    service, _ = _build_service(
        category_expenses=current,
        bedrock_should_fail=True,
    )

    with pytest.raises(BedrockError):
        await service.get_monthly_analysis(user_id, 2025, 6)



# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════

# Hypothesis 전략 정의
category_names = st.sampled_from(["식비", "교통", "문화", "의료", "교육", "주거", "통신", "의류"])
amounts = st.integers(min_value=1000, max_value=5_000_000)
years = st.integers(min_value=2020, max_value=2030)
months = st.integers(min_value=1, max_value=12)


# ──────────────────────────────────────────────
# Property 12: 월간 분석 데이터 구성
# Feature: moneylog-backend-phase7, Property 12: 월간 분석 데이터 구성
# Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    year=years,
    month=months,
    current_amount=amounts,
    prev_amount=amounts,
)
async def test_property_monthly_analysis_data_composition(
    year, month, current_amount, prev_amount
):
    """유효한 연월과 거래 데이터가 있는 사용자에 대해 get_monthly_analysis는
    카테고리별 지출 합계, 전월 대비 증감, 예산 대비 실적을 포함한 분석 결과를 반환해야 한다.
    거래 데이터가 없으면 BadRequestError가 발생해야 한다.

    **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**
    """
    user_id = uuid.uuid4()
    category = "식비"

    # 거래 데이터가 있는 경우: 정상 분석 결과 반환
    current = [{"category": category, "amount": current_amount}]
    prev = [{"category": category, "amount": prev_amount}]

    service, mock_bedrock = _build_service(
        category_expenses=current,
        prev_expenses=prev,
        bedrock_response="분석 결과입니다.",
    )

    result = await service.get_monthly_analysis(user_id, year, month)

    # 12.1: 해당 연월의 지출 데이터를 집계하여 분석 결과 반환
    assert isinstance(result, MonthlyAnalysisResponse)
    assert result.year == year
    assert result.month == month

    # 12.3: AI 응답으로 월간 지출 요약 코멘트 반환
    assert result.summary == "분석 결과입니다."
    assert mock_bedrock.call_count == 1

    # 12.4: 카테고리별 지출 트렌드 반환
    assert len(result.category_trends) == 1
    trend = result.category_trends[0]
    assert trend.category == category
    assert trend.current_amount == current_amount
    assert trend.previous_amount == prev_amount

    # 12.2: 전월 대비 증감 검증
    if current_amount > prev_amount:
        assert trend.direction == "increase"
    elif current_amount < prev_amount:
        assert trend.direction == "decrease"
    else:
        assert trend.direction == "unchanged"

    # 증감률 검증
    if prev_amount > 0:
        expected_rate = round((current_amount - prev_amount) / prev_amount * 100, 1)
        assert trend.change_rate == expected_rate

    # 12.5: 거래 데이터가 없으면 BadRequestError
    empty_service, _ = _build_service(category_expenses=[])
    with pytest.raises(BadRequestError):
        await empty_service.get_monthly_analysis(user_id, year, month)


# ──────────────────────────────────────────────
# Property 13: 절약 제안 분기 처리
# Feature: moneylog-backend-phase7, Property 13: 절약 제안 분기 처리
# Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    year=years,
    month=months,
    budget_amount=st.integers(min_value=100000, max_value=1_000_000),
    actual_amount=st.integers(min_value=1000, max_value=2_000_000),
)
async def test_property_savings_tips_branching(
    year, month, budget_amount, actual_amount
):
    """예산 미설정 시 설정 권유 메시지, 모든 카테고리 예산 이내 시 긍정적 피드백,
    초과 카테고리가 있으면 해당 카테고리 목록과 절약 팁을 반환해야 한다.

    **Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5, 13.6**
    """
    user_id = uuid.uuid4()
    category = "식비"

    # 13.5: 예산 미설정 시 설정 권유 메시지
    no_budget_service = AIAnalysisService(
        stats_repo=MockStatsRepository(),
        budget_repo=MockBudgetRepository(budgets=[]),
        bedrock_client=MockBedrockClient(),
    )
    no_budget_result = await no_budget_service.get_savings_tips(user_id, year, month)
    assert no_budget_result.message == "예산을 설정하면 맞춤형 절약 제안을 받을 수 있습니다"
    assert no_budget_result.over_budget_categories == []
    assert no_budget_result.tips == ""

    # 13.1, 13.2, 13.3, 13.4, 13.6: 예산 설정된 경우
    budgets = [MockBudget(category, budget_amount)]
    expenses = [{"category": category, "amount": actual_amount}]

    bedrock_client = MockBedrockClient(response="절약 팁입니다.")
    service = AIAnalysisService(
        stats_repo=MockStatsRepository(expenses),
        budget_repo=MockBudgetRepository(budgets),
        bedrock_client=bedrock_client,
    )

    result = await service.get_savings_tips(user_id, year, month)

    assert isinstance(result, SavingsTipsResponse)
    assert result.year == year
    assert result.month == month

    if actual_amount > budget_amount:
        # 13.2: 초과 카테고리 목록과 초과 금액 식별
        assert len(result.over_budget_categories) == 1
        obc = result.over_budget_categories[0]
        assert obc.category == category
        assert obc.budget_amount == budget_amount
        assert obc.actual_amount == actual_amount
        assert obc.over_amount == actual_amount - budget_amount
        # 13.3, 13.4: Bedrock 절약 팁 생성
        assert result.tips == "절약 팁입니다."
        assert result.message is None
        assert bedrock_client.call_count == 1
    else:
        # 13.6: 모든 카테고리 예산 이내 시 긍정적 피드백
        assert result.over_budget_categories == []
        assert result.message == "모든 카테고리가 예산 이내입니다. 잘 관리하고 계세요!"
        assert result.tips == ""
        assert bedrock_client.call_count == 0
