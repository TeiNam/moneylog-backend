"""
인증 관련 Pydantic 요청/응답 스키마.

회원가입, 로그인, 이메일 인증, 토큰 갱신 등
인증 API에서 사용하는 요청·응답 모델을 정의한다.
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ──────────────────────────────────────────────
# 요청 스키마
# ──────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """회원가입 요청 스키마."""

    email: EmailStr
    password: str = Field(min_length=8, description="비밀번호 (8자 이상, 영문+숫자 포함)")
    nickname: str = Field(min_length=1, max_length=100, description="닉네임")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """비밀번호 강도 검증: 영문 1개 이상 + 숫자 1개 이상 포함."""
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("비밀번호는 영문자를 1개 이상 포함해야 합니다")
        if not re.search(r"\d", v):
            raise ValueError("비밀번호는 숫자를 1개 이상 포함해야 합니다")
        return v


class LoginRequest(BaseModel):
    """로그인 요청 스키마."""

    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    """이메일 인증 요청 스키마."""

    email: EmailStr
    code: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6자리 숫자 인증 코드",
    )


class ResendVerificationRequest(BaseModel):
    """인증 코드 재발송 요청 스키마."""

    email: EmailStr


class RefreshTokenRequest(BaseModel):
    """토큰 갱신 요청 스키마."""

    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """비밀번호 변경 요청 스키마."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class DeactivateAccountRequest(BaseModel):
    """회원 탈퇴 요청 스키마. 비밀번호 확인 필요."""

    password: str


class UpdateProfileRequest(BaseModel):
    """프로필 수정 요청 스키마. 닉네임과 프로필 이미지를 부분 업데이트한다."""

    nickname: str | None = Field(None, min_length=2, max_length=20, description="닉네임 (2~20자)")
    profile_image: str | None = Field(None, max_length=500, description="프로필 이미지 URL (500자 이내)")


# ──────────────────────────────────────────────
# 응답 스키마
# ──────────────────────────────────────────────


class UserResponse(BaseModel):
    """사용자 정보 응답 스키마."""

    id: UUID
    email: str
    nickname: str
    auth_provider: str
    email_verified: bool
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """로그인 토큰 응답 스키마."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    """액세스 토큰 갱신 응답 스키마."""

    access_token: str
    token_type: str = "bearer"
