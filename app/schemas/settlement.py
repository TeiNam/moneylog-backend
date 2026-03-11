"""
정산(Settlement) 관련 Pydantic 응답 스키마.

가족 카드 사용 현황 및 정산 계산 API에서 사용하는 응답 모델을 정의한다.
"""

from uuid import UUID

from pydantic import BaseModel


# ──────────────────────────────────────────────
# 가족 카드 사용 현황
# ──────────────────────────────────────────────


class MemberAssetExpense(BaseModel):
    """구성원별 결제수단별 지출 데이터."""

    asset_id: UUID | None
    amount: int


class MemberUsage(BaseModel):
    """구성원별 사용 현황."""

    user_id: UUID
    nickname: str
    total_expense: int
    asset_expenses: list[MemberAssetExpense]


class FamilyUsageResponse(BaseModel):
    """가족 카드 사용 현황 응답."""

    year: int
    month: int
    family_total_expense: int
    members: list[MemberUsage]


# ──────────────────────────────────────────────
# 정산 계산
# ──────────────────────────────────────────────


class MemberSettlement(BaseModel):
    """구성원별 정산 데이터."""

    user_id: UUID
    nickname: str
    actual_expense: int
    expense_ratio: float
    share_amount: int
    difference: int


class SettlementTransfer(BaseModel):
    """정산 이체 정보."""

    from_user_id: UUID
    from_nickname: str
    to_user_id: UUID
    to_nickname: str
    amount: int


class SettlementResponse(BaseModel):
    """정산 계산 응답."""

    year: int
    month: int
    family_total_expense: int
    split_method: str
    members: list[MemberSettlement]
    transfers: list[SettlementTransfer]
