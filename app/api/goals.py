"""
목표(Goal) 관련 HTTP 엔드포인트.

목표 생성, 목록 조회, 상세 조회, 수정, 삭제를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.enums import GoalStatus
from app.models.user import User
from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import (
    GoalCreateRequest,
    GoalDetailResponse,
    GoalResponse,
    GoalUpdateRequest,
)
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])


def _build_service(db: AsyncSession) -> GoalService:
    """DB 세션으로 GoalService 인스턴스를 생성한다."""
    return GoalService(GoalRepository(db))


# ──────────────────────────────────────────────
# 목표 생성
# ──────────────────────────────────────────────


@router.post(
    "/",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="목표 생성",
)
async def create_goal(
    body: GoalCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalResponse:
    """새로운 목표를 생성한다."""
    service = _build_service(db)
    goal = await service.create(current_user, body)
    await db.commit()
    return GoalResponse.model_validate(goal)


# ──────────────────────────────────────────────
# 목표 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[GoalResponse],
    summary="목표 목록 조회",
)
async def list_goals(
    status_filter: GoalStatus | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GoalResponse]:
    """사용자의 목표 목록을 조회한다."""
    service = _build_service(db)
    goals = await service.get_list(current_user, status=status_filter)
    return [GoalResponse.model_validate(g) for g in goals]


# ──────────────────────────────────────────────
# 목표 상세 조회
# ──────────────────────────────────────────────


@router.get(
    "/{goal_id}",
    response_model=GoalDetailResponse,
    summary="목표 상세 조회",
)
async def get_goal_detail(
    goal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalDetailResponse:
    """목표 상세 정보를 진행률과 함께 조회한다."""
    service = _build_service(db)
    return await service.get_detail(current_user, goal_id)


# ──────────────────────────────────────────────
# 목표 수정
# ──────────────────────────────────────────────


@router.put(
    "/{goal_id}",
    response_model=GoalResponse,
    summary="목표 수정",
)
async def update_goal(
    goal_id: UUID,
    body: GoalUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalResponse:
    """목표 정보를 수정한다."""
    service = _build_service(db)
    goal = await service.update(current_user, goal_id, body)
    await db.commit()
    return GoalResponse.model_validate(goal)


# ──────────────────────────────────────────────
# 목표 삭제
# ──────────────────────────────────────────────


@router.delete(
    "/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="목표 삭제",
)
async def delete_goal(
    goal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """목표를 삭제한다."""
    service = _build_service(db)
    await service.delete(current_user, goal_id)
    await db.commit()
