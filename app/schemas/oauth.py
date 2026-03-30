"""
OAuth 소셜 로그인 관련 Pydantic 스키마.

OAuth 콜백 요청, 인가 URL 응답, 사용자 프로필 모델을 정의한다.
"""

from pydantic import BaseModel, Field


class OAuthCallbackRequest(BaseModel):
    """OAuth 콜백 요청 스키마."""

    code: str = Field(..., description="OAuth 인가 코드")
    state: str = Field(..., description="CSRF 방어용 OAuth state 파라미터")


class OAuthAuthorizationResponse(BaseModel):
    """OAuth 인가 URL 응답 스키마."""

    authorization_url: str = Field(..., description="OAuth 제공자 인가 URL")
    state: str = Field(..., description="CSRF 방어용 OAuth state 파라미터")


class OAuthUserProfile(BaseModel):
    """OAuth 제공자에서 조회한 사용자 프로필 스키마."""

    email: str | None = None  # Apple 이메일 숨기기 시 None 가능
    nickname: str = Field(..., description="사용자 닉네임")
    profile_image: str | None = None  # 프로필 이미지 URL
    sub: str | None = None  # Apple 고유 사용자 식별자 (sub claim)
    is_private_email: bool = Field(default=False, description="Apple Private Email Relay 여부")
