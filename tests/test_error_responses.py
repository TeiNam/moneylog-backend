"""
에러 응답 통합 단위 테스트.

기존 AppException 서브클래스들의 에러 응답 구조 검증,
RequestValidationError 및 일반 Exception catch-all 핸들러 검증,
production 환경에서 스택 트레이스 미포함 검증을 수행한다.

Requirements: 3.1, 3.3, 3.4, 3.5
"""

import json
from unittest.mock import patch

import pytest
from starlette.requests import Request as StarletteRequest

from app.core.exceptions import (
    AppException,
    BadRequestError,
    ConflictError,
    DuplicateEmailError,
    EmailNotVerifiedError,
    ExternalServiceError,
    ForbiddenError,
    InvalidCredentialsError,
    NotFoundError,
    VerificationCodeExhaustedError,
    VerificationCodeExpiredError,
    VerificationCodeInvalidError,
    app_exception_handler,
    class_name_to_error_code,
    general_exception_handler,
    validation_exception_handler,
)


def _make_request(method: str = "GET", path: str = "/test") -> StarletteRequest:
    """테스트용 가짜 Request 객체를 생성한다."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [],
    }
    return StarletteRequest(scope)


# ---------------------------------------------------------------------------
# 1. 각 AppException 서브클래스의 에러 응답 구조 검증
#    Requirements: 3.1, 3.3
# ---------------------------------------------------------------------------

# 테스트 대상 예외 클래스와 기대 상태 코드 매핑
_EXCEPTION_CASES = [
    (DuplicateEmailError, 409, "DUPLICATE_EMAIL_ERROR"),
    (InvalidCredentialsError, 401, "INVALID_CREDENTIALS_ERROR"),
    (EmailNotVerifiedError, 403, "EMAIL_NOT_VERIFIED_ERROR"),
    (VerificationCodeExpiredError, 400, "VERIFICATION_CODE_EXPIRED_ERROR"),
    (VerificationCodeInvalidError, 400, "VERIFICATION_CODE_INVALID_ERROR"),
    (VerificationCodeExhaustedError, 400, "VERIFICATION_CODE_EXHAUSTED_ERROR"),
    (NotFoundError, 404, "NOT_FOUND_ERROR"),
    (ForbiddenError, 403, "FORBIDDEN_ERROR"),
    (BadRequestError, 400, "BAD_REQUEST_ERROR"),
    (ConflictError, 409, "CONFLICT_ERROR"),
    (ExternalServiceError, 502, "EXTERNAL_SERVICE_ERROR"),
]


@pytest.mark.parametrize(
    "exc_cls, expected_status, expected_code",
    _EXCEPTION_CASES,
    ids=[cls.__name__ for cls, _, _ in _EXCEPTION_CASES],
)
@pytest.mark.asyncio
async def test_app_exception_response_structure(
    exc_cls: type[AppException],
    expected_status: int,
    expected_code: str,
):
    """각 AppException 서브클래스가 {error_code, message, details} 구조로 응답하는지 검증한다."""
    exc = exc_cls()
    request = _make_request()

    response = await app_exception_handler(request, exc)
    body = json.loads(response.body)

    # HTTP 상태 코드 검증
    assert response.status_code == expected_status

    # 응답 구조 검증: error_code, message, details 키 존재
    assert "error_code" in body
    assert "message" in body
    assert "details" in body

    # error_code 값 검증
    assert body["error_code"] == expected_code

    # message가 예외의 detail과 일치
    assert body["message"] == exc.detail

    # AppException의 details는 None
    assert body["details"] is None


# ---------------------------------------------------------------------------
# 2. error_code가 클래스명의 UPPER_SNAKE_CASE 변환값과 일치하는지 검증
#    Requirements: 3.3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "class_name, expected_code",
    [
        ("DuplicateEmailError", "DUPLICATE_EMAIL_ERROR"),
        ("InvalidCredentialsError", "INVALID_CREDENTIALS_ERROR"),
        ("NotFoundError", "NOT_FOUND_ERROR"),
        ("EmailNotVerifiedError", "EMAIL_NOT_VERIFIED_ERROR"),
        ("ExternalServiceError", "EXTERNAL_SERVICE_ERROR"),
        ("BadRequestError", "BAD_REQUEST_ERROR"),
    ],
)
def test_class_name_to_error_code_conversion(class_name: str, expected_code: str):
    """class_name_to_error_code가 CamelCase를 UPPER_SNAKE_CASE로 올바르게 변환하는지 검증한다."""
    assert class_name_to_error_code(class_name) == expected_code


# ---------------------------------------------------------------------------
# 3. RequestValidationError 응답 검증
#    Requirements: 3.1, 3.3
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validation_error_response():
    """RequestValidationError가 error_code: VALIDATION_ERROR, details 배열을 포함하는지 검증한다."""
    from fastapi.exceptions import RequestValidationError

    errors = [
        {"type": "value_error", "loc": ("body", "email"), "msg": "유효한 이메일을 입력하세요", "input": "bad"},
        {"type": "missing", "loc": ("body", "password"), "msg": "필수 항목입니다", "input": None},
    ]
    exc = RequestValidationError(errors=errors)
    request = _make_request(method="POST")

    response = await validation_exception_handler(request, exc)
    body = json.loads(response.body)

    # HTTP 422 상태 코드
    assert response.status_code == 422

    # error_code 검증
    assert body["error_code"] == "VALIDATION_ERROR"

    # message 존재
    assert body["message"] == "입력값 검증에 실패했습니다"

    # details 배열 검증
    assert isinstance(body["details"], list)
    assert len(body["details"]) == 2

    # 각 detail 항목에 field, message 키 존재
    for detail in body["details"]:
        assert "field" in detail
        assert "message" in detail

    # 필드명 검증
    assert body["details"][0]["field"] == "email"
    assert body["details"][1]["field"] == "password"


# ---------------------------------------------------------------------------
# 4. 일반 Exception catch-all 핸들러 검증
#    Requirements: 3.4
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_general_exception_returns_500():
    """일반 Exception이 HTTP 500, error_code: INTERNAL_SERVER_ERROR를 반환하는지 검증한다."""
    exc = RuntimeError("예상치 못한 오류")
    request = _make_request()

    # 개발 환경(기본값)으로 테스트
    response = await general_exception_handler(request, exc)
    body = json.loads(response.body)

    # HTTP 500 상태 코드
    assert response.status_code == 500

    # error_code 검증
    assert body["error_code"] == "INTERNAL_SERVER_ERROR"

    # message 검증
    assert body["message"] == "서버 내부 오류가 발생했습니다"


# ---------------------------------------------------------------------------
# 5. production 환경에서 스택 트레이스 미포함 검증
#    Requirements: 3.5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_production_no_stack_trace():
    """production 환경에서 details에 스택 트레이스가 포함되지 않는지 검증한다."""
    exc = ValueError("운영 환경 오류")
    request = _make_request()

    # APP_ENV=production으로 Settings 모킹
    from app.core.config import Settings

    mock_settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test-secret",
        APP_ENV="production",
    )

    with patch("app.core.config.get_settings", return_value=mock_settings):
        response = await general_exception_handler(request, exc)

    body = json.loads(response.body)

    # HTTP 500 상태 코드
    assert response.status_code == 500
    assert body["error_code"] == "INTERNAL_SERVER_ERROR"

    # production 환경에서 details는 None이어야 한다 (스택 트레이스 미포함)
    assert body["details"] is None


@pytest.mark.asyncio
async def test_development_includes_stack_trace():
    """개발 환경에서 details에 스택 트레이스가 포함되는지 검증한다."""
    exc = ValueError("개발 환경 오류")
    request = _make_request()

    # APP_ENV=development로 Settings 모킹
    from app.core.config import Settings

    mock_settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET_KEY="test-secret",
        APP_ENV="development",
    )

    with patch("app.core.config.get_settings", return_value=mock_settings):
        response = await general_exception_handler(request, exc)

    body = json.loads(response.body)

    # 개발 환경에서 details에 스택 트레이스가 포함되어야 한다
    assert body["details"] is not None
    assert isinstance(body["details"], list)
    assert len(body["details"]) > 0
    assert "trace" in body["details"][0]
