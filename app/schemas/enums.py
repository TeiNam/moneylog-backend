"""
Enum 스키마 메타데이터 정의 모듈.

OpenAPI 스키마에서 Enum 필드에 title과 description을 노출하기 위한
헬퍼 함수와 메타데이터 매핑을 제공한다.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.models.enums import (
    Area,
    AssetType,
    CarType,
    CeremonyDirection,
    CeremonyEventType,
    FeedbackType,
    GoalStatus,
    GoalType,
    GroupRole,
    MessageRole,
    Ownership,
    OwnerType,
    ScanStatus,
    SubscriptionCategory,
    SubscriptionCycle,
    SubscriptionStatus,
    TransactionType,
)


# ---------------------------------------------------------------------------
# Enum 필드 메타데이터 정의
# 각 Enum 클래스에 대한 OpenAPI title/description 매핑
# ---------------------------------------------------------------------------

ENUM_METADATA: dict[type, dict[str, str]] = {
    Area: {
        "title": "거래 영역",
        "description": "거래가 속하는 영역 구분 (일반, 차계부, 구독, 경조사)",
    },
    TransactionType: {
        "title": "거래 유형",
        "description": "수입(INCOME) 또는 지출(EXPENSE) 구분",
    },
    CarType: {
        "title": "차계부 비용 유형",
        "description": "차량 관련 지출의 세부 유형 (주유, 정비, 보험, 세금, 통행료, 주차, 세차, 할부, 기타)",
    },
    CeremonyDirection: {
        "title": "경조사 방향",
        "description": "경조사 금액의 이동 방향 (보낸/받은)",
    },
    CeremonyEventType: {
        "title": "경조사 이벤트 유형",
        "description": "경조사의 종류 (결혼, 장례, 돌잔치, 생일, 집들이, 개업, 명절, 기타)",
    },
    OwnerType: {
        "title": "소유자 유형",
        "description": "데이터의 소유 주체 (사용자 또는 가족 그룹)",
    },
    Ownership: {
        "title": "소유권 구분",
        "description": "자산의 소유권 범위 (개인 또는 공유)",
    },
    AssetType: {
        "title": "자산 유형",
        "description": "결제수단의 종류 (은행 계좌, 신용카드, 체크카드, 현금, 투자, 기타)",
    },
    GroupRole: {
        "title": "그룹 역할",
        "description": "가족 그룹에서 구성원의 역할 (소유자 또는 멤버)",
    },
    SubscriptionCategory: {
        "title": "구독 카테고리",
        "description": "구독 서비스의 분류 (OTT, 음악, 클라우드, 생산성, AI, 게임, 뉴스, 기타)",
    },
    SubscriptionCycle: {
        "title": "구독 결제 주기",
        "description": "구독 서비스의 결제 반복 주기 (월간, 연간, 주간)",
    },
    SubscriptionStatus: {
        "title": "구독 상태",
        "description": "구독 서비스의 현재 상태 (활성, 일시정지, 해지)",
    },
    GoalType: {
        "title": "목표 유형",
        "description": "재무 목표의 종류 (월간 저축, 저축률, 특별 목표)",
    },
    GoalStatus: {
        "title": "목표 상태",
        "description": "재무 목표의 진행 상태 (진행 중, 달성 완료, 실패)",
    },
    MessageRole: {
        "title": "메시지 역할",
        "description": "AI 채팅에서 메시지 발신자의 역할 (사용자 또는 AI 어시스턴트)",
    },
    ScanStatus: {
        "title": "스캔 상태",
        "description": "영수증 OCR 스캔의 처리 상태 (대기 중, 완료, 실패)",
    },
    FeedbackType: {
        "title": "피드백 유형",
        "description": "AI 추출 거래 데이터에 대한 사용자 피드백 종류 (카테고리 수정, 금액 수정, 설명 수정)",
    },
}


def enum_field(enum_cls: type, default: Any = ..., **kwargs: Any) -> Any:
    """Enum 필드에 title, description 메타데이터를 자동 추가하는 헬퍼.

    ENUM_METADATA에 등록된 Enum 클래스의 경우 json_schema_extra로
    title과 description을 OpenAPI 스키마에 노출한다.

    Args:
        enum_cls: Enum 클래스 타입
        default: 필드 기본값 (... 이면 필수 필드)
        **kwargs: Pydantic Field에 전달할 추가 인자

    Returns:
        json_schema_extra가 설정된 Pydantic Field
    """
    meta = ENUM_METADATA.get(enum_cls, {})
    extra: dict[str, Any] = {}
    if meta:
        extra["title"] = meta.get("title", "")
        extra["description"] = meta.get("description", "")

    # 기존 json_schema_extra가 있으면 병합
    existing_extra = kwargs.pop("json_schema_extra", None)
    if existing_extra:
        extra.update(existing_extra)

    return Field(default, json_schema_extra=extra if extra else None, **kwargs)
