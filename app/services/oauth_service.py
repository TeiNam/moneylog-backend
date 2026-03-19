"""
OAuth 2.0 소셜 로그인 서비스.

카카오, 네이버, 구글, 애플 OAuth 제공자를 통한 인증을 처리한다.
인가 코드 → 토큰 교환 → 프로필 조회 → 로그인/가입 → JWT 발급 흐름을 구현한다.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from jose import jwt as jose_jwt

from app.core.config import Settings
from app.core.exceptions import ConflictError, ExternalServiceError
from app.core.security import create_access_token, create_refresh_token
from app.models.enums import OAuthProvider
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.oauth import OAuthUserProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 제공자별 URL 상수
# ---------------------------------------------------------------------------

# 인가 URL
AUTHORIZATION_URLS: dict[OAuthProvider, str] = {
    OAuthProvider.KAKAO: "https://kauth.kakao.com/oauth/authorize",
    OAuthProvider.NAVER: "https://nid.naver.com/oauth2.0/authorize",
    OAuthProvider.GOOGLE: "https://accounts.google.com/o/oauth2/v2/auth",
    OAuthProvider.APPLE: "https://appleid.apple.com/auth/authorize",
}

# 토큰 교환 엔드포인트
TOKEN_ENDPOINTS: dict[OAuthProvider, str] = {
    OAuthProvider.KAKAO: "https://kauth.kakao.com/oauth/token",
    OAuthProvider.NAVER: "https://nid.naver.com/oauth2.0/token",
    OAuthProvider.GOOGLE: "https://oauth2.googleapis.com/token",
    OAuthProvider.APPLE: "https://appleid.apple.com/auth/token",
}

# 프로필 조회 엔드포인트 (Apple은 id_token JWT에서 직접 추출)
PROFILE_ENDPOINTS: dict[OAuthProvider, str] = {
    OAuthProvider.KAKAO: "https://kapi.kakao.com/v2/user/me",
    OAuthProvider.NAVER: "https://openapi.naver.com/v1/nid/me",
    OAuthProvider.GOOGLE: "https://www.googleapis.com/oauth2/v2/userinfo",
}


class OAuthService:
    """OAuth 2.0 소셜 로그인 서비스."""

    def __init__(self, user_repo: UserRepository, settings: Settings) -> None:
        self._user_repo = user_repo
        self._settings = settings

    # ------------------------------------------------------------------
    # 인가 URL 생성
    # ------------------------------------------------------------------

    def get_authorization_url(self, provider: OAuthProvider) -> str:
        """OAuth 제공자의 인가 URL을 반환한다."""
        base_url = AUTHORIZATION_URLS[provider]
        client_id = self._get_client_id(provider)
        redirect_uri = self._get_redirect_uri(provider)

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
        }

        # 제공자별 추가 파라미터
        if provider == OAuthProvider.GOOGLE:
            params["scope"] = "openid email profile"
        elif provider == OAuthProvider.NAVER:
            params["state"] = "moneylog"
        elif provider == OAuthProvider.APPLE:
            params["scope"] = "name email"
            params["response_mode"] = "form_post"

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}?{query_string}"

    # ------------------------------------------------------------------
    # 인증 메인 플로우
    # ------------------------------------------------------------------

    async def authenticate(
        self, provider: OAuthProvider, code: str
    ) -> TokenResponse:
        """
        인가 코드로 OAuth 인증을 수행한다.

        1. 인가 코드 → 액세스 토큰 교환
        2. 액세스 토큰으로 사용자 프로필 조회
        3. 기존 사용자 확인 → 로그인 또는 신규 생성
        4. JWT 토큰 발급

        Raises:
            ConflictError: 이메일/비밀번호로 이미 가입된 계정
            ExternalServiceError: OAuth 제공자 통신 오류
        """
        # 1. 인가 코드 → 토큰 교환
        token_data = await self._exchange_code_for_token(provider, code)

        # 2. 사용자 프로필 조회
        profile = await self._get_user_profile(provider, token_data)

        # 3. 사용자 조회 또는 생성
        # Apple 이메일 숨기기 시 sub claim 기반으로 사용자 식별
        user = None

        if profile.email:
            user = await self._user_repo.get_by_email(profile.email)

        if user is not None:
            # 기존 이메일/비밀번호 사용자 → ConflictError
            if user.auth_provider == "EMAIL" and user.password_hash is not None:
                raise ConflictError(detail="이미 이메일로 가입된 계정입니다")

            # 기존 OAuth 사용자 → 로그인 처리
            await self._user_repo.update(user.id, {
                "last_login_at": datetime.now(timezone.utc),
            })
        else:
            # 신규 사용자 생성
            email = profile.email
            # Apple 이메일 숨기기 시 sub claim 기반 이메일 생성
            if email is None and profile.sub:
                email = f"{profile.sub}@privaterelay.appleid.com"

            nickname = profile.nickname or (email.split("@")[0] if email else "사용자")

            user = await self._user_repo.create({
                "email": email,
                "nickname": nickname,
                "password_hash": None,
                "auth_provider": provider.value,
                "email_verified": True,
                "status": "ACTIVE",
                "profile_image": profile.profile_image,
            })

        # 4. JWT 토큰 발급
        token_data_jwt = {
            "sub": str(user.id),
            "email": user.email,
            "auth_provider": user.auth_provider,
        }
        access_token = create_access_token(token_data_jwt)
        refresh_token = create_refresh_token(token_data_jwt)

        logger.info("OAuth 로그인 성공: provider=%s, user_id=%s", provider.value, user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    # ------------------------------------------------------------------
    # 인가 코드 → 토큰 교환
    # ------------------------------------------------------------------

    async def _exchange_code_for_token(
        self, provider: OAuthProvider, code: str
    ) -> str | dict:
        """
        인가 코드를 액세스 토큰으로 교환한다.

        Apple의 경우:
        - client_secret 대신 JWT를 생성하여 토큰 요청에 사용
        - 응답에서 id_token(JWT)을 함께 반환 (dict 형태)
        기타 제공자: 액세스 토큰 문자열 반환

        Raises:
            ExternalServiceError: OAuth 제공자 통신 오류
        """
        token_url = TOKEN_ENDPOINTS[provider]
        client_id = self._get_client_id(provider)
        redirect_uri = self._get_redirect_uri(provider)

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        }

        # Apple은 JWT client_secret 사용
        if provider == OAuthProvider.APPLE:
            data["client_secret"] = self._generate_apple_client_secret()
        else:
            data["client_secret"] = self._get_client_secret(provider)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()
                token_response = response.json()
        except httpx.HTTPError as exc:
            logger.error("OAuth 토큰 교환 실패: provider=%s, error=%s", provider.value, exc)
            raise ExternalServiceError(
                detail="소셜 로그인 처리 중 오류가 발생했습니다"
            ) from exc

        # Apple은 id_token도 함께 반환
        if provider == OAuthProvider.APPLE:
            return {
                "access_token": token_response.get("access_token", ""),
                "id_token": token_response.get("id_token", ""),
            }

        access_token = token_response.get("access_token")
        if not access_token:
            raise ExternalServiceError(
                detail="소셜 로그인 처리 중 오류가 발생했습니다"
            )
        return access_token

    # ------------------------------------------------------------------
    # 사용자 프로필 조회
    # ------------------------------------------------------------------

    async def _get_user_profile(
        self, provider: OAuthProvider, access_token: str | dict
    ) -> OAuthUserProfile:
        """
        OAuth 사용자 프로필을 조회한다.

        Apple의 경우:
        - 별도 프로필 조회 API를 호출하지 않음
        - id_token(JWT)의 claims에서 사용자 정보를 직접 추출
        기타 제공자: 액세스 토큰으로 프로필 API 호출

        Raises:
            ExternalServiceError: OAuth 제공자 통신 오류
        """
        # Apple: id_token JWT에서 직접 추출
        if provider == OAuthProvider.APPLE:
            assert isinstance(access_token, dict), "Apple 토큰은 dict 형태여야 합니다"
            id_token = access_token.get("id_token", "")
            claims = self._decode_apple_id_token(id_token)

            email = claims.get("email")
            sub = claims.get("sub", "")
            is_private_email = claims.get("is_private_email", False)
            # is_private_email이 문자열 "true"일 수 있음
            if isinstance(is_private_email, str):
                is_private_email = is_private_email.lower() == "true"

            return OAuthUserProfile(
                email=email,
                nickname=email.split("@")[0] if email else f"apple_{sub[:8]}",
                sub=sub,
                is_private_email=is_private_email,
            )

        # 기타 제공자: 프로필 API 호출
        assert isinstance(access_token, str), "액세스 토큰은 문자열이어야 합니다"
        profile_url = PROFILE_ENDPOINTS[provider]

        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(profile_url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("OAuth 프로필 조회 실패: provider=%s, error=%s", provider.value, exc)
            raise ExternalServiceError(
                detail="소셜 로그인 처리 중 오류가 발생했습니다"
            ) from exc

        return self._parse_profile(provider, data)

    # ------------------------------------------------------------------
    # Apple 전용 메서드
    # ------------------------------------------------------------------

    def _generate_apple_client_secret(self) -> str:
        """
        Apple OAuth용 client_secret JWT를 생성한다.

        Apple은 일반적인 client_secret 대신 JWT를 사용한다:
        - Header: alg=ES256, kid=APPLE_KEY_ID
        - Payload: iss=APPLE_TEAM_ID, sub=APPLE_CLIENT_ID,
                   aud=https://appleid.apple.com, exp=5분
        - 서명: APPLE_PRIVATE_KEY (P-256 타원곡선)
        """
        now = datetime.now(timezone.utc)
        payload = {
            "iss": self._settings.APPLE_TEAM_ID,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "aud": "https://appleid.apple.com",
            "sub": self._settings.APPLE_CLIENT_ID,
        }
        headers = {
            "alg": "ES256",
            "kid": self._settings.APPLE_KEY_ID,
        }
        return jose_jwt.encode(
            payload,
            self._settings.APPLE_PRIVATE_KEY,
            algorithm="ES256",
            headers=headers,
        )

    def _decode_apple_id_token(self, id_token: str) -> dict:
        """
        Apple id_token(JWT)을 디코딩하여 claims를 추출한다.

        검증 없이 디코딩한다 (Apple 공개 키 검증은 프로덕션에서 추가 가능).

        추출하는 주요 claims:
        - sub: Apple 고유 사용자 식별자
        - email: 사용자 이메일 (Private Email Relay 시 프록시 이메일)
        - email_verified: 이메일 인증 여부
        - is_private_email: Private Email Relay 사용 여부
        """
        try:
            claims = jose_jwt.get_unverified_claims(id_token)
            return {
                "sub": claims.get("sub", ""),
                "email": claims.get("email"),
                "email_verified": claims.get("email_verified", False),
                "is_private_email": claims.get("is_private_email", False),
            }
        except Exception as exc:
            logger.error("Apple id_token 디코딩 실패: %s", exc)
            raise ExternalServiceError(
                detail="소셜 로그인 처리 중 오류가 발생했습니다"
            ) from exc

    # ------------------------------------------------------------------
    # 제공자별 프로필 파싱
    # ------------------------------------------------------------------

    def _parse_profile(
        self, provider: OAuthProvider, data: dict
    ) -> OAuthUserProfile:
        """제공자별 응답 데이터를 OAuthUserProfile로 변환한다."""
        if provider == OAuthProvider.KAKAO:
            kakao_account = data.get("kakao_account", {})
            profile = kakao_account.get("profile", {})
            return OAuthUserProfile(
                email=kakao_account.get("email"),
                nickname=profile.get("nickname", "카카오사용자"),
                profile_image=profile.get("profile_image_url"),
            )

        if provider == OAuthProvider.NAVER:
            response = data.get("response", {})
            return OAuthUserProfile(
                email=response.get("email"),
                nickname=response.get("nickname", "네이버사용자"),
                profile_image=response.get("profile_image"),
            )

        if provider == OAuthProvider.GOOGLE:
            return OAuthUserProfile(
                email=data.get("email"),
                nickname=data.get("name", "구글사용자"),
                profile_image=data.get("picture"),
            )

        # 도달하지 않아야 하는 분기
        raise ExternalServiceError(detail="지원하지 않는 OAuth 제공자입니다")

    # ------------------------------------------------------------------
    # 헬퍼: 제공자별 설정값 조회
    # ------------------------------------------------------------------

    def _get_client_id(self, provider: OAuthProvider) -> str:
        """제공자별 클라이언트 ID를 반환한다."""
        mapping = {
            OAuthProvider.KAKAO: self._settings.KAKAO_CLIENT_ID,
            OAuthProvider.NAVER: self._settings.NAVER_CLIENT_ID,
            OAuthProvider.GOOGLE: self._settings.GOOGLE_CLIENT_ID,
            OAuthProvider.APPLE: self._settings.APPLE_CLIENT_ID,
        }
        return mapping.get(provider) or ""

    def _get_client_secret(self, provider: OAuthProvider) -> str:
        """제공자별 클라이언트 시크릿을 반환한다."""
        mapping = {
            OAuthProvider.KAKAO: self._settings.KAKAO_CLIENT_SECRET,
            OAuthProvider.NAVER: self._settings.NAVER_CLIENT_SECRET,
            OAuthProvider.GOOGLE: self._settings.GOOGLE_CLIENT_SECRET,
        }
        return mapping.get(provider) or ""

    def _get_redirect_uri(self, provider: OAuthProvider) -> str:
        """제공자별 리다이렉트 URI를 반환한다."""
        mapping = {
            OAuthProvider.KAKAO: self._settings.KAKAO_REDIRECT_URI,
            OAuthProvider.NAVER: self._settings.NAVER_REDIRECT_URI,
            OAuthProvider.GOOGLE: self._settings.GOOGLE_REDIRECT_URI,
            OAuthProvider.APPLE: self._settings.APPLE_REDIRECT_URI,
        }
        return mapping.get(provider) or ""
