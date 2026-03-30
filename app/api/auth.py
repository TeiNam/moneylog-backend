"""
인증 관련 HTTP 엔드포인트.

회원가입, 로그인, 이메일 인증, 인증 코드 재발송, 토큰 갱신, 현재 사용자 조회를 제공한다.
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.rate_limit import rate_limit_dependency
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
from app.services.s3_service import S3Service
from app.core.config import get_settings
from app.core.exceptions import AppException

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
    _rate_limit: None = Depends(rate_limit_dependency),
) -> UserResponse:
    """이메일/비밀번호로 회원가입을 수행한다."""
    repo = UserRepository(db)
    service = EmailAuthService(repo)
    user = await service.register(body.email, body.password, body.nickname)

    # 회원가입 성공 후 기본 카테고리 시드 생성 (비즈니스 로직 실패만 허용, 인프라 오류는 전파)
    try:
        category_service = CategoryService(CategoryRepository(db))
        await category_service.seed_defaults(user.id)
    except AppException:
        logger.warning(
            "기본 카테고리 시드 생성 실패: user_id=%s (회원가입은 정상 처리)",
            user.id,
        )

    # 기본 자산(현금) 시드 생성 및 default_asset_id 설정 (비즈니스 로직 실패만 허용, 인프라 오류는 전파)
    try:
        asset_service = AssetService(AssetRepository(db), repo)
        await asset_service.seed_defaults(user.id)
    except AppException:
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
    _rate_limit: None = Depends(rate_limit_dependency),
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
    _rate_limit: None = Depends(rate_limit_dependency),
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
    # 프로필 이미지 URL이 제공된 경우 S3 도메인 검증
    if body.profile_image is not None:
        settings = get_settings()
        s3_service = S3Service(settings)
        if not s3_service.validate_s3_domain(body.profile_image):
            from app.core.exceptions import BadRequestError
            raise BadRequestError(
                detail="유효하지 않은 프로필 이미지 URL입니다"
            )

    repo = UserRepository(db)
    service = EmailAuthService(repo)
    updated_user = await service.update_profile(current_user, body)
    await db.commit()
    return UserResponse.model_validate(updated_user)


# ---------------------------------------------------------------------------
# OAuth 소셜 로그인 엔드포인트
# ---------------------------------------------------------------------------

from app.models.enums import OAuthProvider
from app.schemas.oauth import OAuthAuthorizationResponse, OAuthCallbackRequest
from app.services.oauth_service import OAuthService


@router.get(
    "/oauth/{provider}/authorize",
    response_model=OAuthAuthorizationResponse,
    summary="OAuth 인가 URL 반환",
)
async def oauth_authorize(provider: OAuthProvider) -> OAuthAuthorizationResponse:
    """OAuth 제공자의 인가 URL을 반환한다."""
    settings = get_settings()
    # OAuthService는 user_repo가 필요하지만 인가 URL 생성에는 불필요
    # 임시 None 전달 (get_authorization_url은 user_repo를 사용하지 않음)
    oauth_service = OAuthService(user_repo=None, settings=settings)  # type: ignore[arg-type]
    authorization_url, state = oauth_service.get_authorization_url(provider)
    return OAuthAuthorizationResponse(authorization_url=authorization_url, state=state)


@router.post(
    "/oauth/{provider}/callback",
    response_model=TokenResponse,
    summary="OAuth 콜백 처리",
)
async def oauth_callback(
    provider: OAuthProvider,
    body: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """OAuth 인가 코드로 로그인/가입을 처리한다."""
    settings = get_settings()
    repo = UserRepository(db)
    oauth_service = OAuthService(user_repo=repo, settings=settings)
    token_response = await oauth_service.authenticate(provider, body.code, expected_state=body.state)
    await db.commit()
    return token_response
