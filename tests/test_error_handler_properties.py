"""
에러 핸들러 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 에러 응답 규격 통일의 핵심 속성을 검증한다.
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from fastapi import Request
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

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
    VerificationCodeExpiredError,
    VerificationCodeExhaustedError,
    VerificationCodeInvalidError,
    app_exception_handler,
    class_name_to_error_code,
    validation_exception_handler,
)


# ---------------------------------------------------------------------------
# 테스트용 전략(Strategy) 정의
# ---------------------------------------------------------------------------

# 기존 AppException 서브클래스 목록
_APP_EXCEPTION_CLASSES = [
    DuplicateEmailError,
    InvalidCredentialsError,
    EmailNotVerifiedError,
    VerificationCodeExpiredError,
    VerificationCodeInvalidError,
    VerificationCodeExhaustedError,
    NotFoundError,
    ForbiddenError,
    BadRequestError,
    ConflictError,
    ExternalServiceError,
]

# AppException 서브클래스 인스턴스를 생성하는 전략
app_exception_strategy = st.sampled_from(_APP_EXCEPTION_CLASSES).flatmap(
    lambda cls: st.builds(cls)
)

# 커스텀 메시지를 가진 AppException 서브클래스 인스턴스 전략
app_exception_with_message_strategy = st.sampled_from(_APP_EXCEPTION_CLASSES).flatmap(
    lambda cls: st.text(min_size=1, max_size=100).map(lambda msg: cls(detail=msg))
)

# 필드명 전략 (유효한 Python 식별자 형태)
field_name_strategy = st.from_regex(r"[a-z][a-z0-9_]{0,29}", fullmatch=True)

# 에러 메시지 전략
error_message_strategy = st.text(min_size=1, max_size=200)


# ---------------------------------------------------------------------------
# Property 5: AppException 에러 응답 구조 및 error_code 변환
# Feature: frontend-integration-improvements, Property 5: AppException 에러 응답 구조 및 error_code 변환
# **Validates: Requirements 3.1, 3.3**
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(exc=app_exception_strategy)
@pytest.mark.asyncio
async def test_app_exception_response_structure_and_error_code(exc: AppException):
    """임의의 AppException 서브클래스 인스턴스에 대해,
    에러 핸들러가 반환하는 JSON 응답은 error_code, message 키를 포함해야 하며,
    error_code는 예외 클래스명의 UPPER_SNAKE_CASE 변환값과 일치해야 한다.
    """
    # 테스트용 가짜 Request 객체 생성
    from starlette.requests import Request as StarletteRequest
    scope = {"type": "http", "method": "GET", "path": "/test", "query_string": b"", "headers": []}
    request = StarletteRequest(scope)

    # 핸들러 호출
    response = await app_exception_handler(request, exc)

    # 응답 본문 파싱
    body = json.loads(response.body)

    # 1) 응답에 error_code, message 키가 존재해야 한다
    assert "error_code" in body, f"error_code 키 누락: {body}"
    assert "message" in body, f"message 키 누락: {body}"

    # 2) error_code는 클래스명의 UPPER_SNAKE_CASE 변환값과 일치해야 한다
    expected_code = class_name_to_error_code(exc.__class__.__name__)
    assert body["error_code"] == expected_code, (
        f"error_code 불일치: {body['error_code']} != {expected_code}"
    )

    # 3) message는 예외의 detail과 일치해야 한다
    assert body["message"] == exc.detail

    # 4) HTTP 상태 코드가 예외의 status_code와 일치해야 한다
    assert response.status_code == exc.status_code


@settings(max_examples=30, deadline=None)
@given(exc=app_exception_with_message_strategy)
@pytest.mark.asyncio
async def test_app_exception_custom_message_preserved(exc: AppException):
    """임의의 커스텀 메시지를 가진 AppException에 대해,
    에러 핸들러 응답의 message가 원본 메시지와 동일해야 한다.
    """
    from starlette.requests import Request as StarletteRequest
    scope = {"type": "http", "method": "GET", "path": "/test", "query_string": b"", "headers": []}
    request = StarletteRequest(scope)

    response = await app_exception_handler(request, exc)
    body = json.loads(response.body)

    assert body["message"] == exc.detail


# ---------------------------------------------------------------------------
# Property 6: ValidationError 에러 응답 구조
# Feature: frontend-integration-improvements, Property 6: ValidationError 에러 응답 구조
# **Validates: Requirements 3.2**
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=None)
@given(
    fields_and_messages=st.lists(
        st.tuples(field_name_strategy, error_message_strategy),
        min_size=1,
        max_size=10,
    )
)
@pytest.mark.asyncio
async def test_validation_error_response_structure(
    fields_and_messages: list[tuple[str, str]],
):
    """임의의 필드명과 오류 메시지 조합으로 구성된 RequestValidationError에 대해,
    핸들러가 반환하는 JSON 응답은 error_code가 "VALIDATION_ERROR"이고,
    details 배열의 각 항목은 field와 message 키를 포함해야 한다.
    """
    from fastapi.exceptions import RequestValidationError

    # RequestValidationError 생성 (Pydantic 유효성 검증 오류 형식)
    errors = [
        {
            "type": "value_error",
            "loc": ("body", field),
            "msg": msg,
            "input": None,
        }
        for field, msg in fields_and_messages
    ]
    exc = RequestValidationError(errors=errors)

    # 테스트용 가짜 Request 객체 생성
    from starlette.requests import Request as StarletteRequest
    scope = {"type": "http", "method": "POST", "path": "/test", "query_string": b"", "headers": []}
    request = StarletteRequest(scope)

    # 핸들러 호출
    response = await validation_exception_handler(request, exc)

    # 응답 본문 파싱
    body = json.loads(response.body)

    # 1) HTTP 상태 코드가 422여야 한다
    assert response.status_code == 422

    # 2) error_code가 "VALIDATION_ERROR"여야 한다
    assert body["error_code"] == "VALIDATION_ERROR"

    # 3) message가 존재해야 한다
    assert "message" in body
    assert body["message"] == "입력값 검증에 실패했습니다"

    # 4) details 배열이 존재하고, 입력 오류 수와 동일한 길이여야 한다
    assert body["details"] is not None
    assert len(body["details"]) == len(fields_and_messages)

    # 5) details 각 항목에 field, message 키가 존재해야 한다
    for detail in body["details"]:
        assert "field" in detail, f"field 키 누락: {detail}"
        assert "message" in detail, f"message 키 누락: {detail}"

    # 6) details의 필드명이 입력 필드명과 일치해야 한다
    expected_fields = [field for field, _ in fields_and_messages]
    actual_fields = [d["field"] for d in body["details"]]
    assert actual_fields == expected_fields
