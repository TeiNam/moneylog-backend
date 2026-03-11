"""
자산(Asset) 관련 HTTP 엔드포인트.

자산 생성, 목록 조회, 수정, 삭제, 기본 자산 설정, 정렬 순서 변경을 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.user_repository import UserRepository
from app.schemas.asset import (
    AssetCreateRequest,
    AssetResponse,
    AssetUpdateRequest,
    DefaultAssetRequest,
    SortOrderItem,
)
from app.services.asset_service import AssetService

router = APIRouter(prefix="/assets", tags=["assets"])


def _build_service(db: AsyncSession) -> AssetService:
    """DB 세션으로 AssetService 인스턴스를 생성한다."""
    return AssetService(AssetRepository(db), UserRepository(db))


# ──────────────────────────────────────────────
# 자산 생성
# ──────────────────────────────────────────────


@router.post(
    "/",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="자산 생성",
)
async def create_asset(
    body: AssetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssetResponse:
    """새로운 자산을 생성한다."""
    service = _build_service(db)
    asset = await service.create(current_user, body)
    await db.commit()
    return AssetResponse.model_validate(asset)


# ──────────────────────────────────────────────
# 자산 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[AssetResponse],
    summary="자산 목록 조회",
)
async def list_assets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AssetResponse]:
    """사용자의 자산 목록을 sort_order 오름차순으로 조회한다."""
    service = _build_service(db)
    assets = await service.get_list(current_user)
    return [AssetResponse.model_validate(a) for a in assets]


# ──────────────────────────────────────────────
# 기본 자산 설정 (/{asset_id} 경로보다 먼저 정의)
# ──────────────────────────────────────────────


@router.put(
    "/default",
    summary="기본 자산 설정",
)
async def set_default_asset(
    body: DefaultAssetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """사용자의 기본 자산을 설정한다."""
    service = _build_service(db)
    await service.set_default(current_user, body)
    await db.commit()
    return {"message": "기본 자산이 설정되었습니다"}


# ──────────────────────────────────────────────
# 정렬 순서 일괄 변경 (/{asset_id} 경로보다 먼저 정의)
# ──────────────────────────────────────────────


@router.put(
    "/sort-order",
    summary="자산 정렬 순서 일괄 변경",
)
async def update_sort_order(
    items: list[SortOrderItem],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """자산 정렬 순서를 일괄 변경한다."""
    service = _build_service(db)
    await service.update_sort_order(current_user, items)
    await db.commit()
    return {"message": "정렬 순서가 변경되었습니다"}


# ──────────────────────────────────────────────
# 자산 수정
# ──────────────────────────────────────────────


@router.put(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="자산 수정",
)
async def update_asset(
    asset_id: UUID,
    body: AssetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssetResponse:
    """자산 정보를 수정한다."""
    service = _build_service(db)
    asset = await service.update(current_user, asset_id, body)
    await db.commit()
    return AssetResponse.model_validate(asset)


# ──────────────────────────────────────────────
# 자산 삭제
# ──────────────────────────────────────────────


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="자산 삭제",
)
async def delete_asset(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """자산을 삭제한다."""
    service = _build_service(db)
    await service.delete(current_user, asset_id)
    await db.commit()
