"""
인증 비즈니스 로직 서비스.

AuthProvider 프로토콜(SSO 확장 인터페이스)과
EmailAuthService(이메일/비밀번호 인증 구현체)를 정의한다.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from app.core.exceptions import (
    BadRequestError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    VerificationCodeExhaustedError,
    VerificationCodeExpiredError,
    VerificationCodeInvalidError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UpdateProfileRequest

logger = logging.getLogger(__name__)

# 인증 코드 유효 기간 (분)
_VERIFICATION_CODE_EXPIRE_MINUTES = 10
# 인증 코드 최대 시도 횟수
_MAX_VERIFICATION_ATTEMPTS = 5


class AuthProvider(Protocol):
    """인증 프로바이더 인터페이스 — SSO 확장 시 이 프로토콜을 구현한다."""

    async def authenticate(self, credentials: dict) -> User: ...
    async def register(self, user_data: dict) -> User: ...


class EmailAuthService:
    """이메일/비밀번호 인증 구현체."""

    def __init__(self, repository: UserRepository) -> None:
        self._repo = repository

    # ------------------------------------------------------------------
    # 회원가입
    # ------------------------------------------------------------------

    async def register(self, email: str, password: str, nickname: str) -> User:
        """
        이메일/비밀번호로 회원가입을 수행한다.

        1. 중복 이메일 검사
        2. 비밀번호 규칙 검증
        3. 비밀번호 해싱 → 사용자 생성
        4. 인증 코드 생성 (6자리 숫자, 10분 유효)
        5. User 반환

        Raises:
            DuplicateEmailError: 이미 등록된 이메일
        """
        # 중복 이메일 검사
        existing = await self._repo.get_by_email(email)
        if existing:
            raise DuplicateEmailError()

        # 비밀번호 규칙 검증 (Pydantic에서 이미 처리되지만 이중 검증)
        if not validate_password(password):
            raise ValueError("비밀번호는 8자 이상, 영문과 숫자를 포함해야 합니다")

        # 사용자 생성
        hashed = hash_password(password)
        user = await self._repo.create({
            "email": email,
            "password_hash": hashed,
            "nickname": nickname,
            "auth_provider": "EMAIL",
            "status": "ACTIVE",
            "email_verified": False,
        })

        # 인증 코드 생성
        code = self._generate_verification_code()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=_VERIFICATION_CODE_EXPIRE_MINUTES
        )
        await self._repo.create_email_verification(user.id, code, expires_at)

        logger.info("회원가입 완료: user_id=%s, email=%s", user.id, email)
        return user

    # ------------------------------------------------------------------
    # 로그인
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> TokenResponse:
        """
        이메일/비밀번호로 로그인하여 토큰을 발급한다.

        Raises:
            InvalidCredentialsError: 이메일 미존재 또는 비밀번호 불일치
            EmailNotVerifiedError: 이메일 미인증 사용자
        """
        # 사용자 조회 (보안: 이메일 존재 여부 노출 방지)
        user = await self._repo.get_by_email(email)
        if not user:
            raise InvalidCredentialsError()

        # 비밀번호 검증
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        # 탈퇴 계정 로그인 거부 (보안: 탈퇴 여부를 노출하지 않기 위해 동일한 에러 사용)
        if user.status == "WITHDRAWN":
            raise InvalidCredentialsError()

        # 이메일 인증 확인
        if not user.email_verified:
            raise EmailNotVerifiedError()

        # 토큰 발급
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # last_login_at 갱신
        await self._repo.update(user.id, {
            "last_login_at": datetime.now(timezone.utc),
        })

        logger.info("로그인 성공: user_id=%s", user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    # ------------------------------------------------------------------
    # 이메일 인증
    # ------------------------------------------------------------------

    async def verify_email(self, email: str, code: str) -> bool:
        """
        이메일 인증 코드를 검증한다.

        Raises:
            InvalidCredentialsError: 사용자 미존재
            VerificationCodeExpiredError: 코드 만료
            VerificationCodeExhaustedError: 시도 횟수 초과 (5회)
            VerificationCodeInvalidError: 잘못된 코드
        """
        user = await self._repo.get_by_email(email)
        if not user:
            raise InvalidCredentialsError()

        verification = await self._repo.get_email_verification(user.id)
        if not verification:
            raise VerificationCodeInvalidError()

        # 만료 확인
        now = datetime.now(timezone.utc)
        if verification.expires_at.replace(tzinfo=timezone.utc) < now:
            await self._repo.invalidate_verification(verification.id)
            raise VerificationCodeExpiredError()

        # 시도 횟수 증가
        new_attempts = await self._repo.increment_verification_attempts(
            verification.id
        )

        # 5회 초과 시 무효화
        if new_attempts > _MAX_VERIFICATION_ATTEMPTS:
            await self._repo.invalidate_verification(verification.id)
            raise VerificationCodeExhaustedError()

        # 코드 비교
        if verification.code != code:
            raise VerificationCodeInvalidError()

        # 인증 성공: email_verified=True 갱신 + 코드 무효화
        await self._repo.update(user.id, {"email_verified": True})
        await self._repo.invalidate_verification(verification.id)

        logger.info("이메일 인증 완료: user_id=%s", user.id)
        return True

    # ------------------------------------------------------------------
    # 인증 코드 재발송
    # ------------------------------------------------------------------

    async def resend_verification(self, email: str) -> bool:
        """
        인증 코드를 재발송한다.
        기존 코드를 전체 무효화하고 새 코드를 생성한다.

        Raises:
            InvalidCredentialsError: 사용자 미존재
        """
        user = await self._repo.get_by_email(email)
        if not user:
            raise InvalidCredentialsError()

        # 기존 코드 전체 무효화
        await self._repo.invalidate_all_verifications(user.id)

        # 새 코드 생성
        code = self._generate_verification_code()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=_VERIFICATION_CODE_EXPIRE_MINUTES
        )
        await self._repo.create_email_verification(user.id, code, expires_at)

        logger.info("인증 코드 재발송: user_id=%s", user.id)
        return True

    # ------------------------------------------------------------------
    # 토큰 갱신
    # ------------------------------------------------------------------

    async def refresh_token(self, refresh_token: str) -> str:
        """
        리프레시 토큰으로 새 액세스 토큰을 발급한다.

        Raises:
            InvalidCredentialsError: 유효하지 않은 토큰 또는 type != "refresh"
        """
        payload = decode_token(refresh_token)

        # type="refresh" 확인
        if payload.get("type") != "refresh":
            raise InvalidCredentialsError(detail="유효하지 않은 토큰입니다")

        # 사용자 조회
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidCredentialsError(detail="유효하지 않은 토큰입니다")

        user = await self._repo.get_by_id(UUID(user_id))
        if not user:
            raise InvalidCredentialsError(detail="유효하지 않은 토큰입니다")

        # 새 액세스 토큰 발급
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider,
        }
        new_access_token = create_access_token(token_data)

        logger.info("토큰 갱신 완료: user_id=%s", user.id)
        return new_access_token

    # ------------------------------------------------------------------
    # 비밀번호 변경
    # ------------------------------------------------------------------

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        """
        비밀번호를 변경한다.

        1. 현재 비밀번호 검증 (bcrypt 비교)
        2. 새 비밀번호 규칙 검증 (8자 이상, 영문 1개 이상, 숫자 1개 이상)
        3. password_hash 갱신

        Raises:
            BadRequestError: 현재 비밀번호 불일치 또는 새 비밀번호 규칙 미충족
        """
        # 현재 비밀번호 검증
        if not user.password_hash or not verify_password(
            current_password, user.password_hash
        ):
            raise BadRequestError("현재 비밀번호가 일치하지 않습니다")

        # 새 비밀번호 규칙 검증
        if not validate_password(new_password):
            raise BadRequestError("비밀번호는 8자 이상, 영문과 숫자를 포함해야 합니다")

        # password_hash 갱신
        new_hash = hash_password(new_password)
        await self._repo.update(user.id, {"password_hash": new_hash})

        logger.info("비밀번호 변경 완료: user_id=%s", user.id)

    # ------------------------------------------------------------------
    # 회원 탈퇴
    # ------------------------------------------------------------------

    async def deactivate_account(self, user: User, password: str) -> None:
        """
        회원 탈퇴(소프트 삭제)를 수행한다.

        1. 비밀번호 검증 (bcrypt 비교)
        2. User.status를 "WITHDRAWN"으로 변경

        Raises:
            BadRequestError: 비밀번호 불일치
        """
        # 비밀번호 검증
        if not user.password_hash or not verify_password(
            password, user.password_hash
        ):
            raise BadRequestError("비밀번호가 일치하지 않습니다")

        # status를 WITHDRAWN으로 변경
        await self._repo.update(user.id, {"status": "WITHDRAWN"})

        logger.info("회원 탈퇴 완료: user_id=%s", user.id)

    async def update_profile(
        self, user: User, data: UpdateProfileRequest
    ) -> User:
        """
        프로필 정보를 부분 업데이트한다.

        data에서 None이 아닌 필드(nickname, profile_image)만 갱신한다.

        Args:
            user: 현재 로그인한 사용자
            data: 업데이트할 프로필 데이터 (nickname, profile_image)

        Returns:
            갱신된 User 객체
        """
        # None이 아닌 필드만 업데이트 딕셔너리에 포함
        update_data = {
            key: value
            for key, value in data.model_dump().items()
            if value is not None
        }

        if not update_data:
            return user

        updated_user = await self._repo.update(user.id, update_data)
        logger.info(
            "프로필 수정 완료: user_id=%s, fields=%s",
            user.id,
            list(update_data.keys()),
        )
        return updated_user



    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_verification_code() -> str:
        """6자리 숫자 인증 코드를 생성한다 (secrets.randbelow 사용)."""
        return f"{secrets.randbelow(1_000_000):06d}"
