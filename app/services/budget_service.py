"""
예산(Budget) 비즈니스 로직 서비스.

예산 CRUD 및 예산 대비 실적 조회를 담당한다.
소유권 기반 권한 검증(본인 소유 확인)을 수행한다.
"""

import calendar
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.budget import Budget
from app.models.user import User
from app.repositories.budget_repository import BudgetRepository
from app.schemas.budget import (
    BudgetCreateRequest,
    BudgetPerformanceResponse,
    BudgetUpdateRequest,
)

logger = logging.getLogger(__name__)


class BudgetService:
    """예산 CRUD 및 예산 대비 실적 조회 서비스."""

    def __init__(
        self,
        budget_repo: BudgetRepository,
        stats_repo=None,
    ) -> None:
        self._repo = budget_repo
        self._stats_repo = stats_repo

    # ──────────────────────────────────────────────
    # 예산 생성
    # ──────────────────────────────────────────────

    async def create(self, user: User, data: BudgetCreateRequest) -> Budget:
        """새 예산을 생성한다. user_id는 현재 사용자로 자동 설정."""
        budget_data = data.model_dump()
        budget_data["user_id"] = user.id
        budget = await self._repo.create(budget_data)
        logger.info("예산 생성 완료: budget_id=%s", budget.id)
        return budget

    # ──────────────────────────────────────────────
    # 예산 목록 조회
    # ──────────────────────────────────────────────

    async def get_list(self, user: User, year: int, month: int) -> list[Budget]:
        """해당 연월의 예산 목록을 반환한다."""
        return await self._repo.get_list_by_user_month(user.id, year, month)

    # ──────────────────────────────────────────────
    # 예산 수정
    # ──────────────────────────────────────────────

    async def update(
        self, user: User, budget_id: UUID, data: BudgetUpdateRequest
    ) -> Budget:
        """예산 정보를 갱신한다. 권한 검증 포함."""
        budget = await self._repo.get_by_id(budget_id)
        self._check_permission(user, budget)

        # None이 아닌 필드만 업데이트 딕셔너리에 포함
        update_data: dict = {}
        for field in ("category", "budget_amount"):
            value = getattr(data, field, None)
            if value is not None:
                update_data[field] = value

        update_data["updated_at"] = datetime.now(timezone.utc)
        updated = await self._repo.update(budget_id, update_data)
        logger.info("예산 수정 완료: budget_id=%s", budget_id)
        return updated

    # ──────────────────────────────────────────────
    # 예산 삭제
    # ──────────────────────────────────────────────

    async def delete(self, user: User, budget_id: UUID) -> None:
        """예산을 삭제한다. 권한 검증 포함."""
        budget = await self._repo.get_by_id(budget_id)
        self._check_permission(user, budget)
        await self._repo.delete(budget_id)
        logger.info("예산 삭제 완료: budget_id=%s", budget_id)

    # ──────────────────────────────────────────────
    # 예산 대비 실적 조회
    # ──────────────────────────────────────────────

    async def get_performance(
        self, user: User, year: int, month: int
    ) -> list[BudgetPerformanceResponse]:
        """예산 대비 실적을 반환한다.

        카테고리별 예산 금액, 실제 지출, 잔여 예산, 소진율을 계산한다.
        """
        budgets = await self._repo.get_list_by_user_month(user.id, year, month)
        if not budgets:
            return []

        # 해당 연월의 시작일과 종료일 계산
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        # 카테고리별 실제 지출 조회
        category_expenses = await self._stats_repo.get_expense_by_category(
            user.id, start_date, end_date
        )
        # dict로 변환: {category: amount}
        expense_map = {item["category"]: item["amount"] for item in category_expenses}

        result = []
        for budget in budgets:
            actual = expense_map.get(budget.category, 0)
            remaining = budget.budget_amount - actual
            usage_rate = (
                round(actual / budget.budget_amount * 100, 1)
                if budget.budget_amount > 0
                else 0.0
            )
            result.append(
                BudgetPerformanceResponse(
                    category=budget.category,
                    budget_amount=budget.budget_amount,
                    actual_amount=actual,
                    remaining=remaining,
                    usage_rate=usage_rate,
                )
            )
        return result

    # ──────────────────────────────────────────────
    # 권한 검증
    # ──────────────────────────────────────────────

    def _check_permission(self, user: User, budget: Budget | None) -> None:
        """사용자가 해당 예산에 접근할 권한이 있는지 검증한다."""
        if budget is None:
            raise NotFoundError("예산을 찾을 수 없습니다")
        if budget.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")
