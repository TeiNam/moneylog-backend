"""
공유 Enum 타입 정의 모듈

모든 도메인에서 공유하는 Enum 타입을 정의한다.
DB에는 VARCHAR로 저장하되, Python 코드에서는 타입 안전성을 위해 str, Enum을 사용한다.
"""

from enum import Enum


class Area(str, Enum):
    """거래 영역 구분"""

    GENERAL = "GENERAL"
    CAR = "CAR"
    SUBSCRIPTION = "SUBSCRIPTION"
    EVENT = "EVENT"


class TransactionType(str, Enum):
    """거래 유형 (수입/지출)"""

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class TransactionSource(str, Enum):
    """거래 입력 출처"""

    MANUAL = "MANUAL"
    AI_CHAT = "AI_CHAT"
    RECEIPT_SCAN = "RECEIPT_SCAN"
    SUBSCRIPTION_AUTO = "SUBSCRIPTION_AUTO"


class CarType(str, Enum):
    """차계부 비용 유형"""

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
    """경조사 방향 (보낸/받은)"""

    SENT = "SENT"
    RECEIVED = "RECEIVED"


class CeremonyEventType(str, Enum):
    """경조사 이벤트 유형"""

    WEDDING = "WEDDING"
    FUNERAL = "FUNERAL"
    FIRST_BIRTHDAY = "FIRST_BIRTHDAY"
    BIRTHDAY = "BIRTHDAY"
    HOUSEWARMING = "HOUSEWARMING"
    OPENING = "OPENING"
    HOLIDAY = "HOLIDAY"
    OTHER = "OTHER"


class OwnerType(str, Enum):
    """소유자 유형 (사용자/가족 그룹)"""

    USER = "USER"
    FAMILY_GROUP = "FAMILY_GROUP"


class Ownership(str, Enum):
    """자산 소유권 구분 (개인/공유)"""

    PERSONAL = "PERSONAL"
    SHARED = "SHARED"


class AssetType(str, Enum):
    """자산(결제수단) 유형"""

    BANK_ACCOUNT = "BANK_ACCOUNT"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    CASH = "CASH"
    INVESTMENT = "INVESTMENT"
    OTHER = "OTHER"


class GroupRole(str, Enum):
    """가족 그룹 내 역할"""

    OWNER = "OWNER"
    MEMBER = "MEMBER"


class SubscriptionCategory(str, Enum):
    """구독 카테고리"""

    OTT = "OTT"
    MUSIC = "MUSIC"
    CLOUD = "CLOUD"
    PRODUCTIVITY = "PRODUCTIVITY"
    AI = "AI"
    GAME = "GAME"
    NEWS = "NEWS"
    OTHER = "OTHER"


class SubscriptionCycle(str, Enum):
    """구독 결제 주기"""

    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    WEEKLY = "WEEKLY"


class SubscriptionStatus(str, Enum):
    """구독 상태"""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class GoalType(str, Enum):
    """목표 유형"""

    MONTHLY_SAVING = "MONTHLY_SAVING"
    SAVING_RATE = "SAVING_RATE"
    SPECIAL = "SPECIAL"


class GoalStatus(str, Enum):
    """목표 상태"""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MessageRole(str, Enum):
    """AI 채팅 메시지 역할"""

    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ScanStatus(str, Enum):
    """영수증 스캔 처리 상태"""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FeedbackType(str, Enum):
    """AI 피드백 유형"""

    CATEGORY_CORRECTION = "CATEGORY_CORRECTION"
    AMOUNT_CORRECTION = "AMOUNT_CORRECTION"
    DESCRIPTION_CORRECTION = "DESCRIPTION_CORRECTION"



