"""
공유 Enum 타입 정의 모듈

모든 도메인에서 공유하는 Enum 타입을 정의한다.
DB에는 VARCHAR로 저장하되, Python 코드에서는 타입 안전성을 위해 str, Enum을 사용한다.
"""

from enum import Enum


class Area(str, Enum):
    """거래 영역 구분.

    거래가 속하는 영역을 나타낸다.
    일반 거래, 차계부, 구독, 경조사 네 가지 영역으로 분류한다.
    """

    GENERAL = "GENERAL"
    CAR = "CAR"
    SUBSCRIPTION = "SUBSCRIPTION"
    EVENT = "EVENT"


class TransactionType(str, Enum):
    """거래 유형 (수입/지출).

    거래의 방향을 나타낸다.
    수입(INCOME) 또는 지출(EXPENSE)로 구분한다.
    """

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class TransactionSource(str, Enum):
    """거래 입력 출처"""

    MANUAL = "MANUAL"
    AI_CHAT = "AI_CHAT"
    RECEIPT_SCAN = "RECEIPT_SCAN"
    SUBSCRIPTION_AUTO = "SUBSCRIPTION_AUTO"


class CarType(str, Enum):
    """차계부 비용 유형.

    차량 관련 지출의 세부 유형을 나타낸다.
    주유, 정비, 보험, 세금, 통행료, 주차, 세차, 할부, 기타로 분류한다.
    """

    FUEL = "FUEL"
    MAINTENANCE = "MAINTENANCE"
    INSURANCE = "INSURANCE"
    TAX = "TAX"
    TOLL = "TOLL"
    PARKING = "PARKING"
    WASH = "WASH"
    INSTALLMENT = "INSTALLMENT"
    OTHER = "OTHER"


class CeremonyDirection(str, Enum):
    """경조사 방향 (보낸/받은).

    경조사 금액의 이동 방향을 나타낸다.
    보낸 경조사비(SENT) 또는 받은 경조사비(RECEIVED)로 구분한다.
    """

    SENT = "SENT"
    RECEIVED = "RECEIVED"


class CeremonyEventType(str, Enum):
    """경조사 이벤트 유형.

    경조사의 종류를 나타낸다.
    결혼, 장례, 돌잔치, 생일, 집들이, 개업, 명절, 기타로 분류한다.
    """

    WEDDING = "WEDDING"
    FUNERAL = "FUNERAL"
    FIRST_BIRTHDAY = "FIRST_BIRTHDAY"
    BIRTHDAY = "BIRTHDAY"
    HOUSEWARMING = "HOUSEWARMING"
    OPENING = "OPENING"
    HOLIDAY = "HOLIDAY"
    OTHER = "OTHER"


class OwnerType(str, Enum):
    """소유자 유형 (사용자/가족 그룹).

    데이터의 소유 주체를 나타낸다.
    개인 사용자(USER) 또는 가족 그룹(FAMILY_GROUP)으로 구분한다.
    """

    USER = "USER"
    FAMILY_GROUP = "FAMILY_GROUP"


class Ownership(str, Enum):
    """자산 소유권 구분 (개인/공유).

    자산의 소유권 범위를 나타낸다.
    개인 소유(PERSONAL) 또는 가족 그룹 공유(SHARED)로 구분한다.
    """

    PERSONAL = "PERSONAL"
    SHARED = "SHARED"


class AssetType(str, Enum):
    """자산(결제수단) 유형.

    결제수단의 종류를 나타낸다.
    은행 계좌, 신용카드, 체크카드, 현금, 투자, 기타로 분류한다.
    """

    BANK_ACCOUNT = "BANK_ACCOUNT"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    CASH = "CASH"
    INVESTMENT = "INVESTMENT"
    OTHER = "OTHER"


class GroupRole(str, Enum):
    """가족 그룹 내 역할.

    가족 그룹에서 구성원의 역할을 나타낸다.
    그룹 소유자(OWNER) 또는 일반 멤버(MEMBER)로 구분한다.
    """

    OWNER = "OWNER"
    MEMBER = "MEMBER"


class SubscriptionCategory(str, Enum):
    """구독 카테고리.

    구독 서비스의 분류를 나타낸다.
    OTT, 음악, 클라우드, 생산성, AI, 게임, 뉴스, 기타로 분류한다.
    """

    OTT = "OTT"
    MUSIC = "MUSIC"
    CLOUD = "CLOUD"
    PRODUCTIVITY = "PRODUCTIVITY"
    AI = "AI"
    GAME = "GAME"
    NEWS = "NEWS"
    OTHER = "OTHER"


class SubscriptionCycle(str, Enum):
    """구독 결제 주기.

    구독 서비스의 결제 반복 주기를 나타낸다.
    월간(MONTHLY), 연간(YEARLY), 주간(WEEKLY)으로 구분한다.
    """

    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    WEEKLY = "WEEKLY"


class SubscriptionStatus(str, Enum):
    """구독 상태.

    구독 서비스의 현재 상태를 나타낸다.
    활성(ACTIVE), 일시정지(PAUSED), 해지(CANCELLED)로 구분한다.
    """

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class GoalType(str, Enum):
    """목표 유형.

    재무 목표의 종류를 나타낸다.
    월간 저축(MONTHLY_SAVING), 저축률(SAVING_RATE), 특별 목표(SPECIAL)로 분류한다.
    """

    MONTHLY_SAVING = "MONTHLY_SAVING"
    SAVING_RATE = "SAVING_RATE"
    SPECIAL = "SPECIAL"


class GoalStatus(str, Enum):
    """목표 상태.

    재무 목표의 진행 상태를 나타낸다.
    진행 중(ACTIVE), 달성 완료(COMPLETED), 실패(FAILED)로 구분한다.
    """

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MessageRole(str, Enum):
    """AI 채팅 메시지 역할.

    AI 채팅에서 메시지 발신자의 역할을 나타낸다.
    사용자(USER) 또는 AI 어시스턴트(ASSISTANT)로 구분한다.
    """

    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ScanStatus(str, Enum):
    """영수증 스캔 처리 상태.

    영수증 OCR 스캔의 처리 진행 상태를 나타낸다.
    대기 중(PENDING), 완료(COMPLETED), 실패(FAILED)로 구분한다.
    """

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FeedbackType(str, Enum):
    """AI 피드백 유형.

    AI가 추출한 거래 데이터에 대한 사용자 피드백 종류를 나타낸다.
    카테고리 수정(CATEGORY_CORRECTION), 금액 수정(AMOUNT_CORRECTION),
    설명 수정(DESCRIPTION_CORRECTION)으로 분류한다.
    """

    CATEGORY_CORRECTION = "CATEGORY_CORRECTION"
    AMOUNT_CORRECTION = "AMOUNT_CORRECTION"
    DESCRIPTION_CORRECTION = "DESCRIPTION_CORRECTION"




class OAuthProvider(str, Enum):
    """OAuth 소셜 로그인 제공자.

    지원하는 소셜 로그인 제공자를 나타낸다.
    카카오(KAKAO), 네이버(NAVER), 구글(GOOGLE), 애플(APPLE)로 구분한다.
    """

    KAKAO = "KAKAO"
    NAVER = "NAVER"
    GOOGLE = "GOOGLE"
    APPLE = "APPLE"
