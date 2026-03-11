"""
이체(Transfer) 비즈니스 로직 서비스.

계좌 간 이체 생성, 조회, 자산 잔액 갱신을 담당한다.
개인 이체(본인 자산 간)와 가족 이체(동일 가족 그룹 구성원 간)를 지원한다.
"""

import logging
from datetime import date
from uuid import UUID

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.asset import Asset
from app.models.transfer import Transfer
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.transfer_repository import TransferRepository
from app.repositories.user_repository import UserRepository
from app.schemas.transfer import (
    TransferCreateData,
    TransferCreateRequest,
    TransferUpdateRequest,
    TransferWithAssetNames,
)

logger = logging.getLogger(__name__)


class TransferService:
    """계좌 간 이체 생성, 조회, 자산 잔액 갱신 서비스."""

    def __init__(
        self,
        transfer_repo: TransferRepository,
        asset_repo: AssetRepository,
        user_repo: UserRepository,
    ) -> None:
        self._transfer_repo = transfer_repo
        self._asset_repo = asset_repo
        self._user_repo = user_repo

    # ──────────────────────────────────────────────
    # 이체 생성
    # ──────────────────────────────────────────────

    async def create(
        self, user: User, data: TransferCreateRequest
    ) -> Transfer:
        """이체를 생성하고 자산 잔액을 갱신한다.

        Args:
            user: 현재 인증된 사용자
            data: 이체 생성 요청 데이터

        Returns:
            생성된 Transfer 객체

        Raises:
            NotFoundError: 자산이 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        # 출금 자산 조회
        from_asset = await self._asset_repo.get_by_id(data.from_asset_id)
        if from_asset is None:
            raise NotFoundError("자산을 찾을 수 없습니다")

        # 입금 자산 조회
        to_asset = await self._asset_repo.get_by_id(data.to_asset_id)
        if to_asset is None:
            raise NotFoundError("자산을 찾을 수 없습니다")

        # 출금 자산 소유권 검증: 반드시 본인 소유여야 함
        if from_asset.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

        # 개인 이체 vs 가족 이체 분기
        family_group_id = None
        if to_asset.user_id == user.id:
            # 개인 이체: 두 자산 모두 본인 소유
            self._validate_personal_transfer(user, from_asset, to_asset)
        else:
            # 가족 이체: 동일 가족 그룹 검증
            family_group_id = await self._validate_family_transfer(
                user, from_asset, to_asset
            )

        # 잔액 갱신: 출금 자산에서 (amount + fee) 차감
        from_new_balance = (from_asset.balance or 0) - (data.amount + data.fee)
        await self._asset_repo.update(
            from_asset.id, {"balance": from_new_balance}
        )

        # 잔액 갱신: 입금 자산에 amount 추가
        to_new_balance = (to_asset.balance or 0) + data.amount
        await self._asset_repo.update(
            to_asset.id, {"balance": to_new_balance}
        )

        # 이체 레코드 생성 — dict 대신 Pydantic 모델로 타입 안전성 확보
        transfer_data = TransferCreateData(
            user_id=user.id,
            family_group_id=family_group_id,
            from_asset_id=data.from_asset_id,
            to_asset_id=data.to_asset_id,
            amount=data.amount,
            fee=data.fee,
            description=data.description,
            transfer_date=data.transfer_date,
        )
        transfer = await self._transfer_repo.create(transfer_data)

        logger.info(
            "이체 생성 완료: transfer_id=%s, from=%s, to=%s, amount=%d",
            transfer.id,
            data.from_asset_id,
            data.to_asset_id,
            data.amount,
        )
        return transfer

    # ──────────────────────────────────────────────
    # 이체 목록 조회
    # ──────────────────────────────────────────────

    async def get_list(
        self,
        user: User,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TransferWithAssetNames]:
        """현재 사용자의 이체 내역을 최신순으로 반환한다.

        각 이체에 from_asset_name, to_asset_name을 포함한다.
        배치 조회로 자산명을 1회 쿼리로 조회하여 N+1 문제를 방지한다.

        Args:
            user: 현재 인증된 사용자
            start_date: 시작일 필터 (선택)
            end_date: 종료일 필터 (선택)

        Returns:
            이체 정보 + 자산명을 포함하는 Pydantic 모델 목록
        """
        transfers = await self._transfer_repo.get_list_by_user(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
        )

        # 모든 자산 ID 수집
        asset_ids: set[UUID] = set()
        for t in transfers:
            asset_ids.add(t.from_asset_id)
            asset_ids.add(t.to_asset_id)

        # 배치 조회 (1회 쿼리)
        assets = await self._asset_repo.get_by_ids(list(asset_ids))
        asset_map = {a.id: a.name for a in assets}

        # 결과 조합
        result = []
        for transfer in transfers:
            result.append(TransferWithAssetNames(
                transfer=transfer,
                from_asset_name=asset_map.get(transfer.from_asset_id, ""),
                to_asset_name=asset_map.get(transfer.to_asset_id, ""),
            ))

        return result

    # ──────────────────────────────────────────────
    # 이체 상세 조회
    # ──────────────────────────────────────────────

    async def get_detail(
        self, user: User, transfer_id: UUID
    ) -> TransferWithAssetNames:
        """이체 상세 정보를 반환한다. 권한 검증 포함.

        Args:
            user: 현재 인증된 사용자
            transfer_id: 조회할 이체 ID

        Returns:
            이체 정보 + 자산명을 포함하는 Pydantic 모델

        Raises:
            NotFoundError: 이체가 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        transfer = await self._transfer_repo.get_by_id(transfer_id)
        if transfer is None:
            raise NotFoundError("이체를 찾을 수 없습니다")

        # 권한 검증: 본인의 이체만 조회 가능
        if transfer.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

        # 자산명 조회
        from_asset_name = await self._get_asset_name(transfer.from_asset_id)
        to_asset_name = await self._get_asset_name(transfer.to_asset_id)

        # dict 대신 Pydantic 모델 인스턴스 반환
        return TransferWithAssetNames(
            transfer=transfer,
            from_asset_name=from_asset_name,
            to_asset_name=to_asset_name,
        )

    # ──────────────────────────────────────────────
    # 이체 수정
    # ──────────────────────────────────────────────

    async def update(
        self, user: User, transfer_id: UUID, data: TransferUpdateRequest
    ) -> Transfer:
        """이체를 수정하고 자산 잔액을 재조정한다.

        1. 기존 이체의 잔액 효과를 원복 (from_asset += old_amount+old_fee, to_asset -= old_amount)
        2. 새로운 값으로 잔액 재계산 (from_asset -= new_amount+new_fee, to_asset += new_amount)
        3. 이체 레코드 갱신

        Args:
            user: 현재 인증된 사용자
            transfer_id: 수정할 이체 ID
            data: 이체 수정 요청 데이터

        Returns:
            갱신된 Transfer 객체

        Raises:
            NotFoundError: 이체가 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        # 이체 조회
        transfer = await self._transfer_repo.get_by_id(transfer_id)
        if transfer is None:
            raise NotFoundError("이체를 찾을 수 없습니다")

        # 권한 검증: 본인 소유 확인
        if transfer.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

        # 출금/입금 자산 조회
        from_asset = await self._asset_repo.get_by_id(transfer.from_asset_id)
        to_asset = await self._asset_repo.get_by_id(transfer.to_asset_id)

        old_amount = transfer.amount
        old_fee = transfer.fee

        # 새 값 결정 (부분 업데이트: 변경되지 않은 필드는 기존 값 유지)
        new_amount = data.amount if data.amount is not None else old_amount
        new_fee = data.fee if data.fee is not None else old_fee

        # 1단계: 기존 잔액 효과 원복
        from_asset_balance = (from_asset.balance or 0) + old_amount + old_fee
        to_asset_balance = (to_asset.balance or 0) - old_amount

        # 2단계: 새 값으로 잔액 재계산
        from_asset_balance -= new_amount + new_fee
        to_asset_balance += new_amount

        # 자산 잔액 갱신
        await self._asset_repo.update(
            from_asset.id, {"balance": from_asset_balance}
        )
        await self._asset_repo.update(
            to_asset.id, {"balance": to_asset_balance}
        )

        # 이체 레코드 갱신 (변경된 필드만)
        update_data = data.model_dump(exclude_unset=True)
        updated_transfer = await self._transfer_repo.update(
            transfer_id, update_data
        )

        logger.info(
            "이체 수정 완료: transfer_id=%s, old_amount=%d, new_amount=%d",
            transfer_id,
            old_amount,
            new_amount,
        )
        return updated_transfer

    # ──────────────────────────────────────────────
    # 이체 삭제
    # ──────────────────────────────────────────────

    async def delete(self, user: User, transfer_id: UUID) -> None:
        """이체를 삭제하고 자산 잔액을 원복한다.

        from_asset += amount + fee, to_asset -= amount

        Args:
            user: 현재 인증된 사용자
            transfer_id: 삭제할 이체 ID

        Raises:
            NotFoundError: 이체가 존재하지 않을 때
            ForbiddenError: 접근 권한이 없을 때
        """
        # 이체 조회
        transfer = await self._transfer_repo.get_by_id(transfer_id)
        if transfer is None:
            raise NotFoundError("이체를 찾을 수 없습니다")

        # 권한 검증: 본인 소유 확인
        if transfer.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

        # 출금/입금 자산 조회
        from_asset = await self._asset_repo.get_by_id(transfer.from_asset_id)
        to_asset = await self._asset_repo.get_by_id(transfer.to_asset_id)

        # 잔액 원복: 출금 자산에 (amount + fee) 복원, 입금 자산에서 amount 차감
        from_new_balance = (from_asset.balance or 0) + transfer.amount + transfer.fee
        to_new_balance = (to_asset.balance or 0) - transfer.amount

        await self._asset_repo.update(
            from_asset.id, {"balance": from_new_balance}
        )
        await self._asset_repo.update(
            to_asset.id, {"balance": to_new_balance}
        )

        # 이체 레코드 삭제
        await self._transfer_repo.delete(transfer_id)

        logger.info(
            "이체 삭제 완료: transfer_id=%s, amount=%d, fee=%d",
            transfer_id,
            transfer.amount,
            transfer.fee,
        )

    # ──────────────────────────────────────────────
    # 개인 이체 검증
    # ──────────────────────────────────────────────

    def _validate_personal_transfer(
        self, user: User, from_asset: Asset, to_asset: Asset
    ) -> None:
        """개인 이체 시 두 자산 모두 본인 소유인지 검증한다.

        Raises:
            ForbiddenError: 자산이 본인 소유가 아닐 때
        """
        if from_asset.user_id != user.id or to_asset.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")

    # ──────────────────────────────────────────────
    # 가족 이체 검증
    # ──────────────────────────────────────────────

    async def _validate_family_transfer(
        self, user: User, from_asset: Asset, to_asset: Asset
    ) -> UUID:
        """가족 이체 시 동일 가족 그룹에 속하는지 검증한다.

        출금 자산은 본인 소유여야 하고, 두 자산 소유자가
        동일 가족 그룹에 속해야 한다.

        Args:
            user: 현재 인증된 사용자
            from_asset: 출금 자산
            to_asset: 입금 자산

        Returns:
            공통 family_group_id

        Raises:
            ForbiddenError: 동일 가족 그룹이 아닐 때
        """
        # 현재 사용자의 family_group_id 확인
        if user.family_group_id is None:
            raise ForbiddenError("접근 권한이 없습니다")

        # 입금 자산 소유자 조회
        to_asset_owner = await self._user_repo.get_by_id(to_asset.user_id)
        if to_asset_owner is None:
            raise ForbiddenError("접근 권한이 없습니다")

        # 동일 가족 그룹 검증
        if (
            to_asset_owner.family_group_id is None
            or to_asset_owner.family_group_id != user.family_group_id
        ):
            raise ForbiddenError("접근 권한이 없습니다")

        return user.family_group_id

    # ──────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────

    async def _get_asset_name(self, asset_id: UUID) -> str:
        """자산 ID로 자산명을 조회한다. 존재하지 않으면 빈 문자열 반환."""
        asset = await self._asset_repo.get_by_id(asset_id)
        if asset is None:
            return ""
        return asset.name
