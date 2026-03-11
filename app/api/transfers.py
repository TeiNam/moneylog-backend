"""
이체(Transfer) 관련 HTTP 엔드포인트.

이체 생성, 목록 조회, 상세 조회를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.transfer_repository import TransferRepository
from app.repositories.user_repository import UserRepository
from app.schemas.transfer import (
    TransferCreateRequest,
    TransferDetailResponse,
    TransferResponse,
    TransferUpdateRequest,
    TransferWithAssetNames,
)
from app.services.transfer_service import TransferService

router = APIRouter(prefix="/transfers", tags=["transfers"])


def _build_service(db: AsyncSession) -> TransferService:
    """DB 세션으로 TransferService 인스턴스를 생성한다."""
    return TransferService(
        transfer_repo=TransferRepository(db),
        asset_repo=AssetRepository(db),
        user_repo=UserRepository(db),
    )


# ──────────────────────────────────────────────
# 이체 생성
# ──────────────────────────────────────────────


@router.post(
    "/",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="이체 생성",
)
async def create_transfer(
    body: TransferCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    """새로운 이체를 생성한다."""
    service = _build_service(db)
    transfer = await service.create(current_user, body)
    await db.commit()
    return TransferResponse.model_validate(transfer)


# ──────────────────────────────────────────────
# 이체 내역 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[TransferDetailResponse],
    summary="이체 내역 목록 조회",
)
async def list_transfers(
    start_date: date | None = Query(None, description="시작일 필터"),
    end_date: date | None = Query(None, description="종료일 필터"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransferDetailResponse]:
    """현재 사용자의 이체 내역을 최신순으로 조회한다."""
    service = _build_service(db)
    items = await service.get_list(current_user, start_date, end_date)
    # 서비스가 TransferWithAssetNames 모델을 반환하므로 속성 접근 사용
    return [
        TransferDetailResponse(
            **TransferResponse.model_validate(item.transfer).model_dump(),
            from_asset_name=item.from_asset_name,
            to_asset_name=item.to_asset_name,
        )
        for item in items
    ]


# ──────────────────────────────────────────────
# 이체 상세 조회
# ──────────────────────────────────────────────


@router.get(
    "/{transfer_id}",
    response_model=TransferDetailResponse,
    summary="이체 상세 조회",
)
async def get_transfer(
    transfer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransferDetailResponse:
    """이체 상세 정보를 조회한다."""
    service = _build_service(db)
    detail = await service.get_detail(current_user, transfer_id)
    # 서비스가 TransferWithAssetNames 모델을 반환하므로 속성 접근 사용
    return TransferDetailResponse(
        **TransferResponse.model_validate(detail.transfer).model_dump(),
        from_asset_name=detail.from_asset_name,
        to_asset_name=detail.to_asset_name,
    )


# ──────────────────────────────────────────────
# 이체 수정
# ──────────────────────────────────────────────


@router.put(
    "/{transfer_id}",
    response_model=TransferResponse,
    summary="이체 수정",
)
async def update_transfer(
    transfer_id: UUID,
    body: TransferUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    """이체를 수정하고 자산 잔액을 재조정한다."""
    service = _build_service(db)
    transfer = await service.update(current_user, transfer_id, body)
    await db.commit()
    return TransferResponse.model_validate(transfer)


# ──────────────────────────────────────────────
# 이체 삭제
# ──────────────────────────────────────────────


@router.delete(
    "/{transfer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="이체 삭제",
)
async def delete_transfer(
    transfer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """이체를 삭제하고 자산 잔액을 원복한다."""
    service = _build_service(db)
    await service.delete(current_user, transfer_id)
    await db.commit()
