"""
경조사 인물(CeremonyPerson) 비즈니스 로직 서비스.

레포지토리 계층을 위임하여 경조사 인물 검색 및 거래 이력 조회를 제공한다.
다른 서비스와 동일한 레이어드 아키텍처 패턴을 따른다.
"""

import logging
from uuid import UUID

from app.models.ceremony_person import CeremonyPerson
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.ceremony_person_repository import CeremonyPersonRepository

logger = logging.getLogger(__name__)


class CeremonyPersonService:
    """경조사 인물 검색 및 거래 이력 조회 서비스."""

    def __init__(self, repo: CeremonyPersonRepository) -> None:
        self._repo = repo

    async def search(
        self, user: User, query: str | None = None
    ) -> list[CeremonyPerson]:
        """사용자의 경조사 인물 목록을 검색한다.

        Args:
            user: 현재 인증된 사용자
            query: 검색어 (이름 또는 관계, None이면 전체 조회)

        Returns:
            검색 조건에 맞는 CeremonyPerson 목록
        """
        return await self._repo.search(user.id, query)

    async def get_transactions(
        self, user: User, person_id: UUID
    ) -> list[Transaction]:
        """특정 경조사 인물의 거래 이력을 조회한다.

        Args:
            user: 현재 인증된 사용자
            person_id: 경조사 인물 ID

        Returns:
            해당 인물의 경조사 거래 목록 (날짜 내림차순)
        """
        return await self._repo.get_transactions_by_person(user.id, person_id)
