"""
거래(Transaction) 관련 HTTP 엔드포인트.

거래 생성, 목록 조회, 단건 상세 조회, 수정, 삭제를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.enums import Area, TransactionType
from app.models.user import User
from app.repositories.ceremony_person_repository import CeremonyPersonRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import (
    CarExpenseDetailSchema,
    CeremonyEventSchema,
    TransactionCreateRequest,
    TransactionDetailResponse,
    TransactionFilterParams,
    TransactionResponse,
    TransactionUpdateRequest,
)
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _build_service(db: AsyncSession) -> TransactionService:
    """DB 세션으로 TransactionService 인스턴스를 생성한다."""
    return TransactionService(
        TransactionRepository(db),
        CeremonyPersonRepository(db),
    )


@router.post(
    "/",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="거래 생성",
)
async def create_transaction(
    body: TransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    """새로운 거래를 생성한다."""
    service = _build_service(db)
    transaction = await service.create(current_user, body)
    await db.commit()
    return TransactionResponse.model_validate(transaction)


@router.get(
    "/",
    response_model=dict,
    summary="거래 목록 조회",
)
async def list_transactions(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    area: Area | None = Query(None),
    type: TransactionType | None = Query(None),
    major_category: str | None = Query(None),
    asset_id: UUID | None = Query(None),
    family_group: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """필터링 및 페이지네이션을 적용하여 거래 목록을 조회한다."""
    filters = TransactionFilterParams(
        start_date=start_date,
        end_date=end_date,
        area=area,
        type=type,
        major_category=major_category,
        asset_id=asset_id,
        family_group=family_group,
        offset=offset,
        limit=limit,
    )
    service = _build_service(db)
    transactions, total = await service.get_list(current_user, filters)
    return {
        "items": [
            TransactionResponse.model_validate(tx) for tx in transactions
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetailResponse,
    summary="거래 단건 조회",
)
async def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionDetailResponse:
    """거래와 관련 상세 데이터(차계부/경조사)를 함께 반환한다."""
    service = _build_service(db)
    detail = await service.get_detail(current_user, transaction_id)
    # Pydantic 모델 속성 접근으로 변경 (dict 접근 대신)
    tx = detail.transaction
    response = TransactionDetailResponse.model_validate(tx)
    if detail.car_detail:
        response.car_detail = CarExpenseDetailSchema.model_validate(
            detail.car_detail, from_attributes=True
        )
    if detail.ceremony_event:
        response.ceremony_event = CeremonyEventSchema.model_validate(
            detail.ceremony_event, from_attributes=True
        )
    return response


@router.put(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="거래 수정",
)
async def update_transaction(
    transaction_id: int,
    body: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    """거래 및 관련 상세 레코드를 갱신한다."""
    service = _build_service(db)
    transaction = await service.update(current_user, transaction_id, body)
    await db.commit()
    return TransactionResponse.model_validate(transaction)


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="거래 삭제",
)
async def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """거래 및 관련 상세 레코드를 삭제한다."""
    service = _build_service(db)
    await service.delete(current_user, transaction_id)
    await db.commit()
