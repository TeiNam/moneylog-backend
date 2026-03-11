"""
목표(Goal) 비즈니스 로직 서비스.

목표 CRUD, 진행률 조회, 상태 관리(ACTIVE → COMPLETED/FAILED)를 담당한다.
소유권 기반 권한 검증(본인 소유 확인)을 수행한다.
"""

import logging
from datetime import date, datetime, timezone
from uuid import UUID

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.enums import GoalStatus
from app.models.goal import Goal
from app.models.user import User
from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import GoalCreateRequest, GoalDetailResponse, GoalUpdateRequest

logger = logging.getLogger(__name__)


class GoalService:
    """목표 CRUD, 진행률 조회, 상태 관리 서비스."""

    def __init__(self, goal_repo: GoalRepository) -> None:
        self._repo = goal_repo

    # ──────────────────────────────────────────────
    # 목표 생성
    # ──────────────────────────────────────────────

    async def create(self, user: User, data: GoalCreateRequest) -> Goal:
        """새 목표를 생성한다. user_id는 현재 사용자로, status는 ACTIVE로 자동 설정."""
        goal_data = data.model_dump()
        goal_data["user_id"] = user.id
        goal_data["status"] = GoalStatus.ACTIVE.value
        # Enum 값을 문자열로 변환
        if hasattr(goal_data.get("type"), "value"):
            goal_data["type"] = goal_data["type"].value
        goal = await self._repo.create(goal_data)
        logger.info("목표 생성 완료: goal_id=%s", goal.id)
        return goal

    # ──────────────────────────────────────────────
    # 목표 목록 조회
    # ──────────────────────────────────────────────

    async def get_list(
        self, user: User, status: GoalStatus | None = None
    ) -> list[Goal]:
        """사용자의 목표 목록을 반환한다. status 필터 선택 적용."""
        status_value = status.value if status is not None else None
        return await self._repo.get_list_by_user(user.id, status=status_value)

    # ──────────────────────────────────────────────
    # 목표 상세 조회
    # ──────────────────────────────────────────────

    async def get_detail(self, user: User, goal_id: UUID) -> GoalDetailResponse:
        """목표 상세 정보와 진행률을 반환한다."""
        goal = await self._repo.get_by_id(goal_id)
        self._check_permission(user, goal)

        # 만료 목표 자동 실패 처리
        goal = await self._check_expiration(goal)

        progress_rate = round(goal.current_amount / goal.target_amount * 100, 1) if goal.target_amount > 0 else 0.0

        return GoalDetailResponse(
            id=goal.id,
            user_id=goal.user_id,
            family_group_id=goal.family_group_id,
            type=goal.type,
            title=goal.title,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            start_date=goal.start_date,
            end_date=goal.end_date,
            status=goal.status,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            progress_rate=progress_rate,
        )

    # ──────────────────────────────────────────────
    # 목표 수정
    # ──────────────────────────────────────────────

    async def update(
        self, user: User, goal_id: UUID, data: GoalUpdateRequest
    ) -> Goal:
        """목표 정보를 갱신한다. COMPLETED/FAILED 상태이면 수정 불가."""
        goal = await self._repo.get_by_id(goal_id)
        self._check_permission(user, goal)

        # COMPLETED/FAILED 상태 수정 불가 (Enum 인스턴스 직접 비교)
        if goal.status in (GoalStatus.COMPLETED, GoalStatus.FAILED):
            raise BadRequestError("완료 또는 실패한 목표는 수정할 수 없습니다")

        update_data: dict = {}
        for field in ("title", "target_amount", "current_amount", "start_date", "end_date"):
            value = getattr(data, field, None)
            if value is not None:
                update_data[field] = value

        update_data["updated_at"] = datetime.now(timezone.utc)
        updated = await self._repo.update(goal_id, update_data)

        # 자동 완료 체크
        updated = await self._check_goal_completion(updated)

        logger.info("목표 수정 완료: goal_id=%s", goal_id)
        return updated

    # ──────────────────────────────────────────────
    # 목표 삭제
    # ──────────────────────────────────────────────

    async def delete(self, user: User, goal_id: UUID) -> None:
        """목표를 삭제한다. 권한 검증 포함."""
        goal = await self._repo.get_by_id(goal_id)
        self._check_permission(user, goal)
        await self._repo.delete(goal_id)
        logger.info("목표 삭제 완료: goal_id=%s", goal_id)

    # ──────────────────────────────────────────────
    # 권한 검증
    # ──────────────────────────────────────────────

    def _check_permission(self, user: User, goal: Goal | None) -> None:
        """사용자가 해당 목표에 접근할 권한이 있는지 검증한다."""
        if goal is None:
            raise NotFoundError("목표를 찾을 수 없습니다")
        if goal.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

    # ──────────────────────────────────────────────
    # 목표 자동 완료 체크
    # ──────────────────────────────────────────────

    async def _check_goal_completion(self, goal: Goal) -> Goal:
        """current_amount >= target_amount이면 status를 COMPLETED로 변경한다."""
        # Enum 인스턴스 직접 비교 (str, Enum 다중 상속으로 .value 불필요)
        if goal.status == GoalStatus.ACTIVE and goal.current_amount >= goal.target_amount:
            updated = await self._repo.update(
                goal.id,
                {"status": GoalStatus.COMPLETED.value, "updated_at": datetime.now(timezone.utc)},
            )
            logger.info("목표 자동 완료: goal_id=%s", goal.id)
            return updated
        return goal

    # ──────────────────────────────────────────────
    # 만료 목표 자동 실패 체크
    # ──────────────────────────────────────────────

    async def _check_expiration(self, goal: Goal) -> Goal:
        """end_date가 오늘 이전이고 ACTIVE이면 status를 FAILED로 변경한다."""
        # Enum 인스턴스 직접 비교 (str, Enum 다중 상속으로 .value 불필요)
        if goal.status == GoalStatus.ACTIVE and goal.end_date < date.today():
            updated = await self._repo.update(
                goal.id,
                {"status": GoalStatus.FAILED.value, "updated_at": datetime.now(timezone.utc)},
            )
            logger.info("목표 자동 실패: goal_id=%s", goal.id)
            return updated
        return goal
