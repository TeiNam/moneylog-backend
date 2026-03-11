"""
가족 그룹(FamilyGroup) 관련 HTTP 엔드포인트.

가족 그룹 생성, 참여, 멤버 관리, 초대 코드 관리, 탈퇴, 해산을 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.family_group_repository import FamilyGroupRepository
from app.repositories.user_repository import UserRepository
from app.schemas.family import (
    FamilyGroupCreateRequest,
    FamilyGroupResponse,
    InviteCodeResponse,
    JoinGroupRequest,
    MemberResponse,
)
from app.services.family_group_service import FamilyGroupService

router = APIRouter(prefix="/family", tags=["family"])


def _build_service(db: AsyncSession) -> FamilyGroupService:
    """DB 세션으로 FamilyGroupService 인스턴스를 생성한다."""
    return FamilyGroupService(FamilyGroupRepository(db), UserRepository(db))


# ──────────────────────────────────────────────
# 가족 그룹 생성
# ──────────────────────────────────────────────


@router.post(
    "/",
    response_model=FamilyGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="가족 그룹 생성",
)
async def create_group(
    body: FamilyGroupCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FamilyGroupResponse:
    """새로운 가족 그룹을 생성한다."""
    service = _build_service(db)
    group = await service.create_group(current_user, body)
    await db.commit()
    return FamilyGroupResponse.model_validate(group)


# ──────────────────────────────────────────────
# 가족 그룹 참여
# ──────────────────────────────────────────────


@router.post(
    "/join",
    response_model=FamilyGroupResponse,
    summary="가족 그룹 참여",
)
async def join_group(
    body: JoinGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FamilyGroupResponse:
    """초대 코드를 입력하여 가족 그룹에 참여한다."""
    service = _build_service(db)
    group = await service.join_group(current_user, body)
    await db.commit()
    return FamilyGroupResponse.model_validate(group)


# ──────────────────────────────────────────────
# 멤버 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/members",
    response_model=list[MemberResponse],
    summary="멤버 목록 조회",
)
async def get_members(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    """소속 가족 그룹의 전체 멤버 목록을 조회한다."""
    service = _build_service(db)
    members = await service.get_members(current_user)
    return [MemberResponse.model_validate(m) for m in members]


# ──────────────────────────────────────────────
# 멤버 강퇴
# ──────────────────────────────────────────────


@router.delete(
    "/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="멤버 강퇴",
)
async def remove_member(
    member_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """OWNER가 특정 멤버를 그룹에서 강퇴한다."""
    service = _build_service(db)
    await service.remove_member(current_user, member_id)
    await db.commit()


# ──────────────────────────────────────────────
# 초대 코드 재생성
# ──────────────────────────────────────────────


@router.post(
    "/invite-code",
    response_model=InviteCodeResponse,
    summary="초대 코드 재생성",
)
async def regenerate_invite_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteCodeResponse:
    """OWNER가 초대 코드를 재생성한다."""
    service = _build_service(db)
    group = await service.regenerate_invite_code(current_user)
    await db.commit()
    return InviteCodeResponse(
        invite_code=group.invite_code,
        invite_code_expires_at=group.invite_code_expires_at,
    )


# ──────────────────────────────────────────────
# 초대 코드 조회
# ──────────────────────────────────────────────


@router.get(
    "/invite-code",
    response_model=InviteCodeResponse,
    summary="초대 코드 조회",
)
async def get_invite_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteCodeResponse:
    """소속 그룹의 초대 코드와 만료 시각을 조회한다."""
    service = _build_service(db)
    group = await service.get_invite_code(current_user)
    return InviteCodeResponse(
        invite_code=group.invite_code,
        invite_code_expires_at=group.invite_code_expires_at,
    )


# ──────────────────────────────────────────────
# 그룹 탈퇴
# ──────────────────────────────────────────────


@router.post(
    "/leave",
    summary="그룹 탈퇴",
)
async def leave_group(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """MEMBER가 가족 그룹에서 탈퇴한다."""
    service = _build_service(db)
    await service.leave_group(current_user)
    await db.commit()
    return {"message": "그룹에서 탈퇴했습니다"}


# ──────────────────────────────────────────────
# 그룹 해산
# ──────────────────────────────────────────────


@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="그룹 해산",
)
async def dissolve_group(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """OWNER가 가족 그룹을 해산한다. 모든 멤버 초기화 후 그룹 삭제."""
    service = _build_service(db)
    await service.dissolve_group(current_user)
    await db.commit()
