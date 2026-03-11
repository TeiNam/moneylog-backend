"""
CeremonyPerson CRUD 레포지토리.

CeremonyPerson 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
경조사 인물의 조회/생성, 누적 금액 갱신, 검색, 거래 이력 조회를 지원한다.
"""

import logging
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ceremony_person import CeremonyPerson
from app.models.transaction import CeremonyEvent, Transaction

logger = logging.getLogger(__name__)


class CeremonyPersonRepository:
    """CeremonyPerson 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, person_id: UUID) -> CeremonyPerson | None:
        """UUID로 경조사 인물을 조회한다."""
        stmt = select(CeremonyPerson).where(CeremonyPerson.id == person_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self, user_id: UUID, name: str, relationship: str
    ) -> CeremonyPerson:
        """이름+관계로 경조사 인물을 조회하거나, 없으면 새로 생성한다.

        Args:
            user_id: 사용자 ID
            name: 인물 이름
            relationship: 관계 (친구, 직장동료 등)

        Returns:
            기존 또는 새로 생성된 CeremonyPerson 객체
        """
        # 기존 인물 조회
        stmt = select(CeremonyPerson).where(
            CeremonyPerson.user_id == user_id,
            CeremonyPerson.name == name,
            CeremonyPerson.relationship == relationship,
        )
        result = await self._session.execute(stmt)
        person = result.scalar_one_or_none()

        if person is not None:
            return person

        # 새 인물 생성 (기본값: total_sent=0, total_received=0, event_count=0)
        person = CeremonyPerson(
            user_id=user_id,
            name=name,
            relationship=relationship,
            total_sent=0,
            total_received=0,
            event_count=0,
        )
        self._session.add(person)
        await self._session.flush()
        await self._session.refresh(person)
        logger.info(
            "경조사 인물 생성 완료: person_id=%s, name=%s", person.id, name
        )
        return person

    async def update_totals(
        self,
        person_id: UUID,
        sent_delta: int,
        received_delta: int,
        count_delta: int,
    ) -> None:
        """경조사 인물의 누적 금액과 이벤트 수를 원자적으로 갱신한다.

        SQL 표현식을 사용하여 동시성 안전한 증감 연산을 수행한다.

        Args:
            person_id: 경조사 인물 ID
            sent_delta: 보낸 금액 증감값
            received_delta: 받은 금액 증감값
            count_delta: 이벤트 수 증감값
        """
        stmt = (
            update(CeremonyPerson)
            .where(CeremonyPerson.id == person_id)
            .values(
                total_sent=CeremonyPerson.total_sent + sent_delta,
                total_received=CeremonyPerson.total_received + received_delta,
                event_count=CeremonyPerson.event_count + count_delta,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info(
            "경조사 인물 누적 갱신: person_id=%s, sent_delta=%d, received_delta=%d, count_delta=%d",
            person_id,
            sent_delta,
            received_delta,
            count_delta,
        )

    async def search(
        self, user_id: UUID, query: str | None = None
    ) -> list[CeremonyPerson]:
        """사용자의 경조사 인물 목록을 검색한다.

        query가 None이면 해당 사용자의 전체 인물 목록을 반환한다.
        query가 있으면 이름 또는 관계에 대해 ILIKE 검색을 수행한다.

        Args:
            user_id: 사용자 ID
            query: 검색어 (이름 또는 관계, None이면 전체 조회)

        Returns:
            검색 조건에 맞는 CeremonyPerson 목록
        """
        stmt = select(CeremonyPerson).where(CeremonyPerson.user_id == user_id)

        if query is not None:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    CeremonyPerson.name.ilike(pattern),
                    CeremonyPerson.relationship.ilike(pattern),
                )
            )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_transactions_by_person(
        self, user_id: UUID, person_id: UUID
    ) -> list[Transaction]:
        """특정 경조사 인물의 거래 이력을 조회한다.

        CeremonyPerson의 이름과 관계를 기반으로 CeremonyEvent와 Transaction을
        조인하여 해당 인물의 경조사 거래 내역을 날짜 내림차순으로 반환한다.

        Args:
            user_id: 사용자 ID
            person_id: 경조사 인물 ID

        Returns:
            해당 인물의 경조사 거래 목록 (날짜 내림차순)
        """
        # 인물 정보 조회
        person = await self.get_by_id(person_id)
        if person is None:
            return []

        # CeremonyEvent와 Transaction을 조인하여 해당 인물의 거래 조회
        stmt = (
            select(Transaction)
            .join(
                CeremonyEvent,
                CeremonyEvent.transaction_id == Transaction.id,
            )
            .where(
                Transaction.user_id == user_id,
                CeremonyEvent.person_name == person.name,
                CeremonyEvent.relationship == person.relationship,
            )
            .order_by(Transaction.date.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
