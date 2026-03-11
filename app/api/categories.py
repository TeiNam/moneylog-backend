"""
카테고리(Category) 관련 HTTP 엔드포인트.

카테고리 생성, 목록 조회, 수정, 삭제, 정렬 순서 변경을 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.enums import Area, TransactionType
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
    SortOrderItem,
)
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


def _build_service(db: AsyncSession) -> CategoryService:
    """DB 세션으로 CategoryService 인스턴스를 생성한다."""
    return CategoryService(CategoryRepository(db))


# ──────────────────────────────────────────────
# 카테고리 생성
# ──────────────────────────────────────────────


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="카테고리 생성",
)
async def create_category(
    body: CategoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """새로운 대분류 카테고리를 생성한다."""
    service = _build_service(db)
    category = await service.create(current_user, body)
    await db.commit()
    return CategoryResponse.model_validate(category)


# ──────────────────────────────────────────────
# 카테고리 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[CategoryResponse],
    summary="카테고리 목록 조회",
)
async def list_categories(
    area: Area | None = Query(None),
    type: TransactionType | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    """영역(area)과 유형(type)으로 필터링하여 카테고리 목록을 조회한다."""
    service = _build_service(db)
    categories = await service.get_list(current_user, area=area, type=type)
    return [CategoryResponse.model_validate(cat) for cat in categories]


# ──────────────────────────────────────────────
# 정렬 순서 일괄 변경 (/{category_id} 경로보다 먼저 정의)
# ──────────────────────────────────────────────


@router.put(
    "/sort-order",
    summary="카테고리 정렬 순서 일괄 변경",
)
async def update_sort_order(
    items: list[SortOrderItem],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """카테고리 정렬 순서를 일괄 변경한다."""
    service = _build_service(db)
    await service.update_sort_order(current_user, items)
    await db.commit()
    return {"message": "정렬 순서가 변경되었습니다"}


# ──────────────────────────────────────────────
# 카테고리 수정
# ──────────────────────────────────────────────


@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="카테고리 수정",
)
async def update_category(
    category_id: UUID,
    body: CategoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    """카테고리 정보를 수정한다."""
    service = _build_service(db)
    category = await service.update(current_user, category_id, body)
    await db.commit()
    return CategoryResponse.model_validate(category)


# ──────────────────────────────────────────────
# 카테고리 삭제
# ──────────────────────────────────────────────


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="카테고리 삭제",
)
async def delete_category(
    category_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """카테고리를 삭제한다. 기본 카테고리는 삭제할 수 없다."""
    service = _build_service(db)
    await service.delete(current_user, category_id)
    await db.commit()
