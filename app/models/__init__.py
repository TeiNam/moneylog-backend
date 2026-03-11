"""SQLAlchemy 모델 패키지."""

from app.models.base import Base
from app.models.user import EmailVerification, User

# Phase 2 모델: 거래, 차계부 상세, 경조사 이벤트
from app.models.transaction import CarExpenseDetail, CeremonyEvent, Transaction

# Phase 2 모델: 경조사 인물
from app.models.ceremony_person import CeremonyPerson

# Phase 2 모델: 카테고리 설정
from app.models.category_config import CategoryConfig

# Phase 3 모델: 자산, 가족 그룹
from app.models.asset import Asset
from app.models.family_group import FamilyGroup

# Phase 4 모델: 구독, 알림
from app.models.subscription import Subscription
from app.models.notification import Notification

# Phase 5 모델: 예산, 목표
from app.models.budget import Budget
from app.models.goal import Goal

# Phase 6 모델: 이체
from app.models.transfer import Transfer

# Phase 7 모델: AI 채팅, 영수증 스캔, AI 피드백
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.receipt_scan import ReceiptScan
from app.models.ai_feedback import AIFeedback

__all__ = [
    "Base",
    "User",
    "EmailVerification",
    "Transaction",
    "CarExpenseDetail",
    "CeremonyEvent",
    "CeremonyPerson",
    "CategoryConfig",
    "Asset",
    "FamilyGroup",
    "Subscription",
    "Notification",
    "Budget",
    "Goal",
    "Transfer",
    "ChatSession",
    "ChatMessage",
    "ReceiptScan",
    "AIFeedback",
]
