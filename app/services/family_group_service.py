"""
가족 그룹(FamilyGroup) 비즈니스 로직 서비스.

가족 그룹 생성, 참여, 멤버 관리, 초대 코드 관리, 탈퇴, 해산을 담당한다.
역할 기반 권한 검증(OWNER/MEMBER)을 수행한다.
"""

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.family_group import FamilyGroup
from app.models.user import User
from app.repositories.family_group_repository import FamilyGroupRepository
from app.repositories.user_repository import UserRepository
from app.schemas.family import FamilyGroupCreateRequest, JoinGroupRequest

logger = logging.getLogger(__name__)

# 초대 코드 설정 상수
_INVITE_CODE_LENGTH = 8
_INVITE_CODE_EXPIRY_DAYS = 7
_INVITE_CODE_CHARS = string.ascii_uppercase + string.digits


class FamilyGroupService:
    """가족 그룹 생성, 참여, 멤버 관리, 해산 서비스."""

    def __init__(
        self,
        family_repo: FamilyGroupRepository,
        user_repo: UserRepository,
    ) -> None:
        self._repo = family_repo
        self._user_repo = user_repo

    # ──────────────────────────────────────────────
    # 그룹 생성
    # ──────────────────────────────────────────────

    async def create_group(
        self, user: User, data: FamilyGroupCreateRequest
    ) -> FamilyGroup:
        """가족 그룹을 생성한다. 초대 코드 자동 생성, 생성자를 OWNER로 설정.

        Args:
            user: 현재 인증된 사용자
            data: 그룹 생성 요청 데이터

        Returns:
            생성된 FamilyGroup 객체

        Raises:
            BadRequestError: 이미 가족 그룹에 소속된 경우
        """
        if user.family_group_id is not None:
            raise BadRequestError("이미 가족 그룹에 소속되어 있습니다")

        # 8자리 영숫자 초대 코드 생성
        invite_code = self._generate_invite_code()
        invite_code_expires_at = self._get_invite_code_expiry()

        # 그룹 생성
        group = await self._repo.create({
            "name": data.name,
            "invite_code": invite_code,
            "invite_code_expires_at": invite_code_expires_at,
            "owner_id": user.id,
        })

        # 생성자의 가족 그룹 정보 설정
        await self._user_repo.update(user.id, {
            "family_group_id": group.id,
            "role_in_group": "OWNER",
        })

        logger.info(
            "가족 그룹 생성 완료: group_id=%s, owner_id=%s",
            group.id,
            user.id,
        )
        return group

    # ──────────────────────────────────────────────
    # 그룹 참여
    # ──────────────────────────────────────────────

    async def join_group(
        self, user: User, data: JoinGroupRequest
    ) -> FamilyGroup:
        """초대 코드로 가족 그룹에 참여한다. 사용자를 MEMBER로 설정.

        Args:
            user: 현재 인증된 사용자
            data: 그룹 참여 요청 데이터

        Returns:
            참여한 FamilyGroup 객체

        Raises:
            BadRequestError: 이미 가족 그룹에 소속된 경우
            NotFoundError: 유효하지 않은 초대 코드인 경우
            BadRequestError: 초대 코드가 만료된 경우
        """
        if user.family_group_id is not None:
            raise BadRequestError("이미 가족 그룹에 소속되어 있습니다")

        # 초대 코드로 그룹 조회
        group = await self._repo.get_by_invite_code(data.invite_code)
        if group is None:
            raise NotFoundError("유효하지 않은 초대 코드입니다")

        # 초대 코드 만료 확인
        if group.invite_code_expires_at < datetime.now(timezone.utc):
            raise BadRequestError("초대 코드가 만료되었습니다")

        # 사용자의 가족 그룹 정보 설정
        await self._user_repo.update(user.id, {
            "family_group_id": group.id,
            "role_in_group": "MEMBER",
        })

        logger.info(
            "가족 그룹 참여 완료: group_id=%s, user_id=%s",
            group.id,
            user.id,
        )
        return group

    # ──────────────────────────────────────────────
    # 멤버 목록 조회
    # ──────────────────────────────────────────────

    async def get_members(self, user: User) -> list[User]:
        """소속 가족 그룹의 전체 멤버 목록을 반환한다.

        Args:
            user: 현재 인증된 사용자

        Returns:
            그룹 소속 멤버 목록

        Raises:
            BadRequestError: 가족 그룹에 소속되어 있지 않은 경우
        """
        if user.family_group_id is None:
            raise BadRequestError("가족 그룹에 소속되어 있지 않습니다")

        return await self._user_repo.get_members_by_group(
            user.family_group_id
        )

    # ──────────────────────────────────────────────
    # 멤버 강퇴
    # ──────────────────────────────────────────────

    async def remove_member(self, user: User, member_id: UUID) -> None:
        """OWNER가 멤버를 강퇴한다. 대상의 family_group_id를 null로 초기화.

        Args:
            user: 현재 인증된 사용자 (OWNER)
            member_id: 강퇴할 멤버 ID

        Raises:
            BadRequestError: 가족 그룹에 소속되어 있지 않은 경우
            ForbiddenError: OWNER가 아닌 경우
            BadRequestError: 자기 자신을 강퇴하려는 경우
        """
        if user.family_group_id is None:
            raise BadRequestError("가족 그룹에 소속되어 있지 않습니다")

        if user.role_in_group != "OWNER":
            raise ForbiddenError("그룹장만 멤버를 강퇴할 수 있습니다")

        if member_id == user.id:
            raise BadRequestError("그룹장은 자신을 강퇴할 수 없습니다")

        await self._user_repo.clear_family_group(member_id)

        logger.info(
            "멤버 강퇴 완료: group_id=%s, member_id=%s",
            user.family_group_id,
            member_id,
        )

    # ──────────────────────────────────────────────
    # 그룹 탈퇴
    # ──────────────────────────────────────────────

    async def leave_group(self, user: User) -> None:
        """MEMBER가 그룹에서 탈퇴한다.

        Args:
            user: 현재 인증된 사용자 (MEMBER)

        Raises:
            BadRequestError: 가족 그룹에 소속되어 있지 않은 경우
            BadRequestError: OWNER가 탈퇴를 시도하는 경우
        """
        if user.family_group_id is None:
            raise BadRequestError("가족 그룹에 소속되어 있지 않습니다")

        if user.role_in_group == "OWNER":
            raise BadRequestError(
                "그룹장은 탈퇴할 수 없습니다. 그룹 해산을 이용해주세요"
            )

        await self._user_repo.clear_family_group(user.id)

        logger.info(
            "그룹 탈퇴 완료: group_id=%s, user_id=%s",
            user.family_group_id,
            user.id,
        )

    # ──────────────────────────────────────────────
    # 초대 코드 재생성
    # ──────────────────────────────────────────────

    async def regenerate_invite_code(self, user: User) -> FamilyGroup:
        """OWNER가 초대 코드를 재생성한다. 유효기간 7일.

        Args:
            user: 현재 인증된 사용자 (OWNER)

        Returns:
            갱신된 FamilyGroup 객체

        Raises:
            BadRequestError: 가족 그룹에 소속되어 있지 않은 경우
            ForbiddenError: OWNER가 아닌 경우
        """
        if user.family_group_id is None:
            raise BadRequestError("가족 그룹에 소속되어 있지 않습니다")

        if user.role_in_group != "OWNER":
            raise ForbiddenError("그룹장만 초대 코드를 재생성할 수 있습니다")

        # 새 초대 코드 생성
        new_code = self._generate_invite_code()
        new_expiry = self._get_invite_code_expiry()

        group = await self._repo.update(user.family_group_id, {
            "invite_code": new_code,
            "invite_code_expires_at": new_expiry,
        })

        logger.info(
            "초대 코드 재생성 완료: group_id=%s",
            user.family_group_id,
        )
        return group

    # ──────────────────────────────────────────────
    # 초대 코드 조회
    # ──────────────────────────────────────────────

    async def get_invite_code(self, user: User) -> FamilyGroup:
        """소속 그룹의 초대 코드와 만료 시각을 반환한다.

        Args:
            user: 현재 인증된 사용자

        Returns:
            FamilyGroup 객체 (invite_code, invite_code_expires_at 포함)

        Raises:
            BadRequestError: 가족 그룹에 소속되어 있지 않은 경우
        """
        if user.family_group_id is None:
            raise BadRequestError("가족 그룹에 소속되어 있지 않습니다")

        return await self._repo.get_by_id(user.family_group_id)

    # ──────────────────────────────────────────────
    # 그룹 해산
    # ──────────────────────────────────────────────

    async def dissolve_group(self, user: User) -> None:
        """OWNER가 그룹을 해산한다. 모든 멤버 초기화 후 그룹 삭제.

        Args:
            user: 현재 인증된 사용자 (OWNER)

        Raises:
            BadRequestError: 가족 그룹에 소속되어 있지 않은 경우
            ForbiddenError: OWNER가 아닌 경우
        """
        if user.family_group_id is None:
            raise BadRequestError("가족 그룹에 소속되어 있지 않습니다")

        if user.role_in_group != "OWNER":
            raise ForbiddenError("그룹장만 그룹을 해산할 수 있습니다")

        group_id = user.family_group_id

        # 모든 멤버의 가족 그룹 정보 초기화
        await self._user_repo.clear_family_group_for_all(group_id)

        # 그룹 레코드 삭제
        await self._repo.delete(group_id)

        logger.info("가족 그룹 해산 완료: group_id=%s", group_id)

    # ──────────────────────────────────────────────
    # 초대 코드 생성 헬퍼
    # ──────────────────────────────────────────────

    @staticmethod
    def _generate_invite_code() -> str:
        """8자리 영숫자(대문자 + 숫자) 초대 코드를 생성한다."""
        return "".join(
            secrets.choice(_INVITE_CODE_CHARS)
            for _ in range(_INVITE_CODE_LENGTH)
        )

    @staticmethod
    def _get_invite_code_expiry() -> datetime:
        """초대 코드 만료 시각 (현재 시각 + 7일)을 반환한다."""
        return datetime.now(timezone.utc) + timedelta(
            days=_INVITE_CODE_EXPIRY_DAYS
        )
