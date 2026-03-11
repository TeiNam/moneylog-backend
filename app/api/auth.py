"""
인증 관련 HTTP 엔드포인트.

회원가입, 로그인, 이메일 인증, 인증 코드 재발송, 토큰 갱신, 현재 사용자 조회를 제공한다.
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AccessTokenResponse,
    ChangePasswordRequest,
    DeactivateAccountRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResendVerificationRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import EmailAuthService
from app.services.asset_service import AssetService
from app.services.category_service import CategoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """이메일/비밀번호로 회원가입을 수행한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    user = await service.register(body.email, body.password, body.nickname)

    # 회원가입 성공 후 기본 카테고리 시드 생성 (실패해도 회원가입은 유지)
    try:
        category_service = CategoryService(CategoryRepository(db))
        await category_service.seed_defaults(user.id)
    except Exception:
        logger.warning(
            "기본 카테고리 시드 생성 실패: user_id=%s (회원가입은 정상 처리)",
            user.id,
        )

    # 기본 자산(현금) 시드 생성 및 default_asset_id 설정 (실패해도 회원가입은 유지)
    try:
        asset_service = AssetService(AssetRepository(db), repo)
        await asset_service.seed_defaults(user.id)
    except Exception:
        logger.warning(
            "기본 자산 시드 생성 실패: user_id=%s (회원가입은 정상 처리)",
            user.id,
        )

    await db.commit()
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="로그인",
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """이메일/비밀번호로 로그인하여 토큰을 발급한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    token_response = await service.login(body.email, body.password)
    await db.commit()
    return token_response


@router.post(
    "/verify-email",
    summary="이메일 인증",
)
async def verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """이메일 인증 코드를 검증한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    await service.verify_email(body.email, body.code)
    await db.commit()
    return {"message": "이메일 인증이 완료되었습니다"}


@router.post(
    "/resend-verification",
    summary="인증 코드 재발송",
)
async def resend_verification(
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """인증 코드를 재발송한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    await service.resend_verification(body.email)
    await db.commit()
    return {"message": "인증 코드가 재발송되었습니다"}


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="토큰 갱신",
)
async def refresh_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """리프레시 토큰으로 새 액세스 토큰을 발급한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    new_access_token = await service.refresh_token(body.refresh_token)
    return AccessTokenResponse(access_token=new_access_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="현재 사용자 정보",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """현재 인증된 사용자의 정보를 반환한다."""
    return UserResponse.model_validate(current_user)

@router.put(
    "/password",
    summary="비밀번호 변경",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """현재 비밀번호를 확인한 후 새 비밀번호로 변경한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    await service.change_password(current_user, body.current_password, body.new_password)
    await db.commit()
    return {"message": "비밀번호가 변경되었습니다"}


@router.delete(
    "/account",
    summary="회원 탈퇴",
)
async def deactivate_account(
    body: DeactivateAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """비밀번호를 확인한 후 계정을 비활성화(소프트 삭제)한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    await service.deactivate_account(current_user, body.password)
    await db.commit()
    return {"message": "회원 탈퇴가 완료되었습니다"}


@router.patch(
    "/profile",
    response_model=UserResponse,
    summary="프로필 수정",
)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """닉네임, 프로필 이미지 등 사용자 프로필 정보를 수정한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    updated_user = await service.update_profile(current_user, body)
    await db.commit()
    return UserResponse.model_validate(updated_user)

