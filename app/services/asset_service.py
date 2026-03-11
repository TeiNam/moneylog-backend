"""
자산(Asset) 비즈니스 로직 서비스.

자산 CRUD, 기본 자산 설정, 시드 데이터 생성, 정렬 순서 변경을 담당한다.
소유권 기반 권한 검증(개인 자산: 본인만, 공유 자산: 그룹 소속 확인)을 수행한다.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.asset import Asset
from app.models.enums import AssetType, Ownership
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.user_repository import UserRepository
from app.schemas.asset import (
    AssetCreateRequest,
    AssetUpdateRequest,
    DefaultAssetRequest,
    SortOrderItem,
)

logger = logging.getLogger(__name__)


class AssetService:
    """자산 CRUD, 기본 자산 설정, 시드 데이터 생성 서비스."""

    def __init__(
        self,
        asset_repo: AssetRepository,
        user_repo: UserRepository,
    ) -> None:
        self._repo = asset_repo
        self._user_repo = user_repo

    # ──────────────────────────────────────────────
    # 기본 자산 시드 생성
    # ──────────────────────────────────────────────

    async def seed_defaults(self, user_id: UUID) -> Asset:
        """회원가입 시 기본 자산(현금)을 생성하고 default_asset_id를 설정한다.

        Args:
            user_id: 새로 가입한 사용자 ID

        Returns:
            생성된 기본 자산(현금) 객체
        """
        # 기본 자산 "현금" 생성
        asset = await self._repo.create({
            "user_id": user_id,
            "ownership": Ownership.PERSONAL.value,
            "name": "현금",
            "asset_type": AssetType.CASH.value,
            "sort_order": 0,
            "icon": "💵",
            "color": "#4CAF50",
        })

        # 사용자의 default_asset_id 설정
        await self._user_repo.update(
            user_id, {"default_asset_id": asset.id}
        )

        logger.info(
            "기본 자산 시드 생성 완료: user_id=%s, asset_id=%s",
            user_id,
            asset.id,
        )
        return asset

    # ──────────────────────────────────────────────
    # 자산 생성
    # ──────────────────────────────────────────────

    async def create(self, user: User, data: AssetCreateRequest) -> Asset:
        """새 자산을 생성한다. user_id는 현재 사용자로 자동 설정.

        Args:
            user: 현재 인증된 사용자
            data: 자산 생성 요청 데이터

        Returns:
            생성된 Asset 객체
        """
        # 현재 사용자의 자산 목록에서 최대 sort_order 조회
        existing = await self._repo.get_list_by_user(
            user.id, user.family_group_id
        )
        next_sort_order = len(existing)

        # family_group_id 결정: 요청에 있으면 사용, SHARED이면 사용자의 그룹 ID
        family_group_id = data.family_group_id
        if (
            family_group_id is None
            and data.ownership == Ownership.SHARED
            and user.family_group_id is not None
        ):
            family_group_id = user.family_group_id

        asset = await self._repo.create({
            "user_id": user.id,
            "family_group_id": family_group_id,
            "ownership": data.ownership.value,
            "name": data.name,
            "asset_type": data.asset_type.value,
            "institution": data.institution,
            "balance": data.balance,
            "memo": data.memo,
            "icon": data.icon,
            "color": data.color,
            "sort_order": next_sort_order,
        })

        logger.info("자산 생성 완료: asset_id=%s", asset.id)
        return asset

    # ──────────────────────────────────────────────
    # 자산 목록 조회
    # ──────────────────────────────────────────────

    async def get_list(self, user: User) -> list[Asset]:
        """사용자의 개인 자산 + 소속 가족 그룹 공유 자산을 sort_order 오름차순으로 반환.

        Args:
            user: 현재 인증된 사용자

        Returns:
            sort_order 오름차순으로 정렬된 자산 목록
        """
        return await self._repo.get_list_by_user(
            user.id, user.family_group_id
        )

    # ──────────────────────────────────────────────
    # 자산 수정
    # ──────────────────────────────────────────────

    async def update(
        self,
        user: User,
        asset_id: UUID,
        data: AssetUpdateRequest,
    ) -> Asset:
        """자산 정보를 갱신한다. 권한 검증 포함.

        Args:
            user: 현재 인증된 사용자
            asset_id: 수정할 자산 ID
            data: 자산 수정 요청 데이터

        Returns:
            갱신된 Asset 객체

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        asset = await self._repo.get_by_id(asset_id)
        if asset is None:
            raise NotFoundError("자산을 찾을 수 없습니다")

        self._check_permission(user, asset)

        # None이 아닌 필드만 업데이트 딕셔너리에 포함
        update_data: dict = {}
        for field in (
            "name",
            "asset_type",
            "institution",
            "balance",
            "memo",
            "icon",
            "color",
            "is_active",
        ):
            value = getattr(data, field, None)
            if value is not None:
                # Enum 값은 문자열로 변환 (isinstance로 정확한 타입 판별)
                update_data[field] = (
                    value.value if isinstance(value, Enum) else value
                )

        # updated_at 설정
        update_data["updated_at"] = datetime.now(timezone.utc)

        updated = await self._repo.update(asset_id, update_data)
        logger.info("자산 수정 완료: asset_id=%s", asset_id)
        return updated

    # ──────────────────────────────────────────────
    # 자산 삭제
    # ──────────────────────────────────────────────

    async def delete(self, user: User, asset_id: UUID) -> None:
        """자산을 삭제한다. 권한 검증 포함.

        Args:
            user: 현재 인증된 사용자
            asset_id: 삭제할 자산 ID

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        asset = await self._repo.get_by_id(asset_id)
        if asset is None:
            raise NotFoundError("자산을 찾을 수 없습니다")

        self._check_permission(user, asset)

        await self._repo.delete(asset_id)
        logger.info("자산 삭제 완료: asset_id=%s", asset_id)

    # ──────────────────────────────────────────────
    # 기본 자산 설정
    # ──────────────────────────────────────────────

    async def set_default(self, user: User, data: DefaultAssetRequest) -> None:
        """사용자의 기본 자산을 설정한다.

        Args:
            user: 현재 인증된 사용자
            data: 기본 자산 설정 요청 데이터

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        asset = await self._repo.get_by_id(data.asset_id)
        if asset is None:
            raise NotFoundError("자산을 찾을 수 없습니다")

        # 접근 가능한 자산인지 검증
        self._check_permission(user, asset)

        # 사용자의 default_asset_id 갱신
        await self._user_repo.update(
            user.id, {"default_asset_id": data.asset_id}
        )

        logger.info(
            "기본 자산 설정 완료: user_id=%s, asset_id=%s",
            user.id,
            data.asset_id,
        )

    # ──────────────────────────────────────────────
    # 정렬 순서 일괄 변경
    # ──────────────────────────────────────────────

    async def update_sort_order(
        self, user: User, items: list[SortOrderItem]
    ) -> None:
        """자산 정렬 순서를 일괄 갱신한다.

        Args:
            user: 현재 인증된 사용자
            items: 정렬 순서 변경 항목 목록
        """
        for item in items:
            await self._repo.update_sort_order(item.asset_id, item.sort_order)

        logger.info("자산 정렬 순서 변경 완료: %d건", len(items))

    # ──────────────────────────────────────────────
    # 권한 검증
    # ──────────────────────────────────────────────

    def _check_permission(self, user: User, asset: Asset) -> None:
        """사용자가 해당 자산에 접근할 권한이 있는지 검증한다.

        - 개인 자산(PERSONAL): 본인 소유인 경우만 허용
        - 공유 자산(SHARED): 같은 가족 그룹에 소속된 경우만 허용

        Raises:
            ForbiddenError: 접근 권한이 없을 때
        """
        # 개인 자산: 본인 소유 확인 (Enum 인스턴스 직접 비교)
        if asset.ownership == Ownership.PERSONAL and asset.user_id == user.id:
            return

        # 공유 자산: 같은 가족 그룹 소속 확인 (Enum 인스턴스 직접 비교)
        if (
            asset.ownership == Ownership.SHARED
            and user.family_group_id is not None
            and asset.family_group_id == user.family_group_id
        ):
            return

        raise ForbiddenError("접근 권한이 없습니다")
