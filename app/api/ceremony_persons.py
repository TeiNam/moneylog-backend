"""
경조사 인물(CeremonyPerson) 관련 HTTP 엔드포인트.

인물 목록 검색 및 특정 인물의 거래 이력 조회를 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.ceremony_person_repository import CeremonyPersonRepository
from app.schemas.ceremony_person import CeremonyPersonResponse
from app.schemas.transaction import TransactionResponse
from app.services.ceremony_person_service import CeremonyPersonService

router = APIRouter(prefix="/ceremony-persons", tags=["ceremony-persons"])


def _build_service(db: AsyncSession) -> CeremonyPersonService:
    """DB 세션으로 CeremonyPersonService 인스턴스를 생성한다."""
    return CeremonyPersonService(CeremonyPersonRepository(db))


@router.get(
    "/",
    response_model=list[CeremonyPersonResponse],
    summary="경조사 인물 목록 검색",
)
async def search_ceremony_persons(
    query: str | None = Query(None, description="이름 또는 관계 검색어"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CeremonyPersonResponse]:
    """사용자의 경조사 인물 목록을 이름 또는 관계로 검색한다."""
    service = _build_service(db)
    persons = await service.search(current_user, query)
    return [CeremonyPersonResponse.model_validate(p) for p in persons]


@router.get(
    "/{person_id}/transactions",
    response_model=list[TransactionResponse],
    summary="특정 인물 거래 이력 조회",
)
async def get_person_transactions(
    person_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionResponse]:
    """특정 경조사 인물의 거래 이력을 날짜 내림차순으로 조회한다."""
    service = _build_service(db)
    transactions = await service.get_transactions(current_user, person_id)
    return [TransactionResponse.model_validate(tx) for tx in transactions]
