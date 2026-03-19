"""
커스텀 예외 클래스 및 전역 예외 핸들러 정의.

모든 도메인 예외는 AppException을 상속하며,
FastAPI 전역 예외 핸들러에서 HTTP 응답으로 변환된다.
"""

import logging
import re
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """기본 애플리케이션 예외. 모든 커스텀 예외의 부모 클래스."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class DuplicateEmailError(AppException):
    """이미 등록된 이메일로 회원가입 시도 시 발생 (409 Conflict)."""

    def __init__(self, detail: str = "이미 등록된 이메일입니다") -> None:
        super().__init__(status_code=409, detail=detail)


class InvalidCredentialsError(AppException):
    """잘못된 이메일 또는 비밀번호로 로그인 시도 시 발생 (401 Unauthorized)."""

    def __init__(self, detail: str = "이메일 또는 비밀번호가 올바르지 않습니다") -> None:
        super().__init__(status_code=401, detail=detail)


class EmailNotVerifiedError(AppException):
    """이메일 인증이 완료되지 않은 사용자의 로그인 시도 시 발생 (403 Forbidden)."""

    def __init__(self, detail: str = "이메일 인증이 필요합니다") -> None:
        super().__init__(status_code=403, detail=detail)


class VerificationCodeExpiredError(AppException):
    """만료된 인증 코드 제출 시 발생 (400 Bad Request)."""

    def __init__(self, detail: str = "인증 코드가 만료되었습니다") -> None:
        super().__init__(status_code=400, detail=detail)


class VerificationCodeInvalidError(AppException):
    """잘못된 인증 코드 제출 시 발생 (400 Bad Request)."""

    def __init__(self, detail: str = "잘못된 인증 코드입니다") -> None:
        super().__init__(status_code=400, detail=detail)


class VerificationCodeExhaustedError(AppException):
    """인증 코드 시도 횟수 초과 시 발생 (400 Bad Request)."""

    def __init__(
        self, detail: str = "인증 코드가 무효화되었습니다. 새로운 코드를 요청해주세요"
    ) -> None:
        super().__init__(status_code=400, detail=detail)


class NotFoundError(AppException):
    """요청한 리소스를 찾을 수 없을 때 발생 (404 Not Found)."""

    def __init__(self, detail: str = "리소스를 찾을 수 없습니다") -> None:
        super().__init__(status_code=404, detail=detail)


class ForbiddenError(AppException):
    """접근 권한이 없을 때 발생 (403 Forbidden)."""

    def __init__(self, detail: str = "접근 권한이 없습니다") -> None:
        super().__init__(status_code=403, detail=detail)


class BadRequestError(AppException):
    """잘못된 요청 시 발생 (400 Bad Request)."""

    def __init__(self, detail: str = "잘못된 요청입니다") -> None:
        super().__init__(status_code=400, detail=detail)


class ConflictError(AppException):
    """리소스 충돌 시 발생 (409 Conflict)."""

    def __init__(self, detail: str = "이미 처리된 요청입니다") -> None:
        super().__init__(status_code=409, detail=detail)


class ExternalServiceError(AppException):
    """외부 서비스(S3, OAuth 제공자) 통신 오류 (502 Bad Gateway)."""

    def __init__(self, detail: str = "외부 서비스 연동 중 오류가 발생했습니다") -> None:
        super().__init__(status_code=502, detail=detail)


def class_name_to_error_code(class_name: str) -> str:
    """클래스명(CamelCase)을 UPPER_SNAKE_CASE 에러 코드로 변환한다.

    예: DuplicateEmailError → DUPLICATE_EMAIL_ERROR
        InvalidCredentialsError → INVALID_CREDENTIALS_ERROR
        NotFoundError → NOT_FOUND_ERROR
    """
    # 대문자 앞에 언더스코어를 삽입하고 전체를 대문자로 변환
    snake = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", class_name)
    # 연속 대문자 처리 (예: HTTPError → HTTP_ERROR)
    snake = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", snake)
    return snake.upper()


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """AppException을 통일된 에러 응답 구조로 변환하는 전역 예외 핸들러."""
    logger.warning(
        "AppException 발생: status_code=%d, detail=%s, path=%s",
        exc.status_code,
        exc.detail,
        request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": class_name_to_error_code(exc.__class__.__name__),
            "message": exc.detail,
            "details": None,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """RequestValidationError를 통일된 에러 응답 구조로 변환하는 핸들러."""
    # 필드별 오류 정보를 {field, message} 배열로 변환
    details = []
    for error in exc.errors():
        # loc 튜플에서 필드명 추출 (body → 필드명 순서)
        loc = error.get("loc", ())
        field = ".".join(str(part) for part in loc if part != "body")
        details.append({
            "field": field,
            "message": error.get("msg", ""),
        })

    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "입력값 검증에 실패했습니다",
            "details": details,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """예상치 못한 예외를 통일된 에러 응답 구조로 변환하는 catch-all 핸들러.

    production 환경에서는 스택 트레이스를 포함하지 않는다.
    """
    from app.core.config import get_settings

    logger.error(
        "처리되지 않은 예외 발생: %s, path=%s",
        str(exc),
        request.url.path,
        exc_info=True,
    )

    settings = get_settings()
    details = None

    # 개발/스테이징 환경에서만 스택 트레이스 포함
    if settings.APP_ENV != "production":
        details = [{"trace": traceback.format_exc()}]

    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "서버 내부 오류가 발생했습니다",
            "details": details,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """FastAPI 앱에 전역 예외 핸들러를 등록한다.

    등록 순서: RequestValidationError → AppException → Exception
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, general_exception_handler)  # type: ignore[arg-type]
