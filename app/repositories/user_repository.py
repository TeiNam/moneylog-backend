"""
User CRUD 레포지토리.

User 및 EmailVerification 모델에 대한 데이터 접근 계층.
AsyncSession을 생성자에서 받아 모든 쿼리를 비동기로 처리한다.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import EmailVerification, User

logger = logging.getLogger(__name__)


class UserRepository:
    """User 및 EmailVerification 데이터 접근 레포지토리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_data: dict) -> User:
        """사용자를 생성하고 반환한다."""
        user = User(**user_data)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        logger.info("사용자 생성 완료: user_id=%s", user.id)
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        """UUID로 사용자를 조회한다."""
        stmt = select(User).where(User.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """이메일로 사용자를 조회한다."""
        stmt = select(User).where(User.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, user_id: UUID, update_data: dict) -> User:
        """사용자 정보를 갱신하고 반환한다."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(**update_data)
            .returning(User)
        )
        result = await self._session.execute(stmt)
        user = result.scalar_one()
        await self._session.flush()
        logger.info("사용자 정보 갱신: user_id=%s", user_id)
        return user

    async def create_email_verification(
        self, user_id: UUID, code: str, expires_at: datetime
    ) -> EmailVerification:
        """이메일 인증 코드를 생성한다."""
        verification = EmailVerification(
            user_id=user_id,
            code=code,
            expires_at=expires_at,
        )
        self._session.add(verification)
        await self._session.flush()
        await self._session.refresh(verification)
        logger.info("인증 코드 생성: user_id=%s", user_id)
        return verification

    async def get_email_verification(
        self, user_id: UUID
    ) -> EmailVerification | None:
        """최신 유효 인증 코드를 조회한다 (is_valid=True, 최신순)."""
        stmt = (
            select(EmailVerification)
            .where(
                EmailVerification.user_id == user_id,
                EmailVerification.is_valid.is_(True),
            )
            .order_by(EmailVerification.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_verification_attempts(
        self, verification_id: UUID
    ) -> int:
        """인증 시도 횟수를 1 증가시키고 새 attempts 값을 반환한다."""
        stmt = (
            update(EmailVerification)
            .where(EmailVerification.id == verification_id)
            .values(attempts=EmailVerification.attempts + 1)
            .returning(EmailVerification.attempts)
        )
        result = await self._session.execute(stmt)
        new_attempts = result.scalar_one()
        await self._session.flush()
        return new_attempts

    async def invalidate_verification(self, verification_id: UUID) -> None:
        """인증 코드를 무효화한다 (is_valid=False)."""
        stmt = (
            update(EmailVerification)
            .where(EmailVerification.id == verification_id)
            .values(is_valid=False)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("인증 코드 무효화: verification_id=%s", verification_id)

    async def invalidate_all_verifications(self, user_id: UUID) -> None:
        """사용자의 모든 인증 코드를 무효화한다."""
        stmt = (
            update(EmailVerification)
            .where(
                EmailVerification.user_id == user_id,
                EmailVerification.is_valid.is_(True),
            )
            .values(is_valid=False)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("사용자의 모든 인증 코드 무효화: user_id=%s", user_id)

    async def get_members_by_group(self, family_group_id: UUID) -> list[User]:
        """가족 그룹 ID로 소속 멤버 목록을 조회한다."""
        stmt = select(User).where(User.family_group_id == family_group_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def clear_family_group(self, user_id: UUID) -> None:
        """특정 사용자의 가족 그룹 정보를 초기화한다."""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(family_group_id=None, role_in_group="MEMBER")
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("사용자 가족 그룹 초기화: user_id=%s", user_id)

    async def clear_family_group_for_all(self, family_group_id: UUID) -> None:
        """특정 그룹의 모든 멤버에 대해 가족 그룹 정보를 초기화한다."""
        stmt = (
            update(User)
            .where(User.family_group_id == family_group_id)
            .values(family_group_id=None, role_in_group="MEMBER")
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("그룹 전체 멤버 가족 그룹 초기화: family_group_id=%s", family_group_id)

