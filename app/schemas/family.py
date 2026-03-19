"""
가족 그룹(FamilyGroup) 관련 Pydantic 요청/응답 스키마.

가족 그룹 생성, 참여, 멤버 조회, 초대 코드 관리 등
가족 그룹 API에서 사용하는 요청·응답 모델을 정의한다.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDatetimeResponse


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class FamilyGroupCreateRequest(BaseModel):
    """가족 그룹 생성 요청 스키마."""

    name: str = Field(..., min_length=1, max_length=50, description="그룹 이름")


class JoinGroupRequest(BaseModel):
    """가족 그룹 참여 요청 스키마."""

    invite_code: str = Field(
        ..., min_length=8, max_length=8, description="8자리 영숫자 초대 코드"
    )


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class FamilyGroupResponse(UTCDatetimeResponse):
    """가족 그룹 응답 스키마."""

    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemberResponse(UTCDatetimeResponse):
    """멤버 응답 스키마."""

    id: UUID
    nickname: str
    email: str
    role_in_group: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InviteCodeResponse(UTCDatetimeResponse):
    """초대 코드 응답 스키마."""

    invite_code: str
    invite_code_expires_at: datetime
