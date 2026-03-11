"""
정산(Settlement) 비즈니스 로직 서비스.

가족 카드 사용 현황 집계 및 정산 계산을 담당한다.
순수 함수로 정산 로직을 분리하여 테스트 용이성을 확보한다.
"""

import logging
from uuid import UUID

from app.core.exceptions import BadRequestError, ForbiddenError
from app.models.user import User
from app.repositories.stats_repository import StatsRepository
from app.repositories.user_repository import UserRepository
from app.schemas.settlement import (
    FamilyUsageResponse,
    MemberAssetExpense,
    MemberSettlement,
    MemberUsage,
    SettlementResponse,
    SettlementTransfer,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# 순수 함수 (DB 없이 독립 테스트 가능)
# ══════════════════════════════════════════════


def parse_ratio(ratio: str, member_count: int) -> list[float]:
    """비율 문자열을 파싱하여 정규화된 비율 리스트로 반환한다."""
    parts = [int(p.strip()) for p in ratio.split(":")]
    if len(parts) != member_count:
        raise BadRequestError("비율 수가 가족 구성원 수와 일치하지 않습니다")
    total = sum(parts)
    return [p / total for p in parts]


def calculate_settlement_transfers(
    members: list[dict], shares: list[int]
) -> list[dict]:
    """정산 차액을 계산하고 이체 방향을 결정한다."""
    diffs = []
    for i, member in enumerate(members):
        diff = member["actual_expense"] - shares[i]
        diffs.append({
            "user_id": member["user_id"],
            "nickname": member["nickname"],
            "diff": diff,
        })

    # 양수(돌려받을 사람)와 음수(지불할 사람) 분리
    creditors = [d for d in diffs if d["diff"] > 0]
    debtors = [d for d in diffs if d["diff"] < 0]

    transfers = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        amount = min(-debtors[i]["diff"], creditors[j]["diff"])
        transfers.append({
            "from_user_id": debtors[i]["user_id"],
            "from_nickname": debtors[i]["nickname"],
            "to_user_id": creditors[j]["user_id"],
            "to_nickname": creditors[j]["nickname"],
            "amount": amount,
        })
        debtors[i]["diff"] += amount
        creditors[j]["diff"] -= amount
        if debtors[i]["diff"] == 0:
            i += 1
        if creditors[j]["diff"] == 0:
            j += 1

    return transfers


class SettlementService:
    """가족 카드 사용 현황 집계 및 정산 계산 서비스."""

    def __init__(
        self,
        stats_repo: StatsRepository,
        user_repo: UserRepository,
    ) -> None:
        self._stats_repo = stats_repo
        self._user_repo = user_repo

    def _validate_family_access(self, user: User) -> None:
        """가족 그룹 접근 권한을 검증한다."""
        if user.family_group_id is None:
            raise BadRequestError("가족 그룹에 소속되어 있지 않습니다")

    async def get_family_usage(
        self, user: User, year: int, month: int
    ) -> FamilyUsageResponse:
        """가족 그룹 내 구성원별 월간 지출 현황을 반환한다.

        비밀 거래(is_private=true)는 StatsRepository에서 제외됨 (Phase 6)
        """
        self._validate_family_access(user)

        # 가족 구성원 조회
        members = await self._user_repo.get_members_by_group(user.family_group_id)

        # 구성원별 결제수단별 지출 조회
        asset_expenses = await self._stats_repo.get_family_member_expenses_by_asset(
            user.family_group_id, year, month
        )

        # 구성원별 총 지출 조회
        member_expenses = await self._stats_repo.get_family_member_expenses(
            user.family_group_id, year, month
        )
        expense_map = {item["user_id"]: item["amount"] for item in member_expenses}

        # 구성원별 결제수단별 지출 매핑
        asset_map: dict[UUID, list[MemberAssetExpense]] = {}
        for item in asset_expenses:
            uid = item["user_id"]
            if uid not in asset_map:
                asset_map[uid] = []
            asset_map[uid].append(
                MemberAssetExpense(asset_id=item["asset_id"], amount=item["amount"])
            )

        # 응답 구성
        member_usages = []
        family_total = 0
        for member in members:
            total = expense_map.get(member.id, 0)
            family_total += total
            member_usages.append(
                MemberUsage(
                    user_id=member.id,
                    nickname=member.nickname,
                    total_expense=total,
                    asset_expenses=asset_map.get(member.id, []),
                )
            )

        return FamilyUsageResponse(
            year=year,
            month=month,
            family_total_expense=family_total,
            members=member_usages,
        )

    async def calculate_settlement(
        self, user: User, year: int, month: int, ratio: str | None = None
    ) -> SettlementResponse:
        """가족 구성원 간 정산 결과를 반환한다.

        비밀 거래(is_private=true)는 StatsRepository에서 제외됨 (Phase 6)
        """
        self._validate_family_access(user)

        # 가족 구성원 조회
        members = await self._user_repo.get_members_by_group(user.family_group_id)

        # 구성원별 지출 조회
        member_expenses = await self._stats_repo.get_family_member_expenses(
            user.family_group_id, year, month
        )
        expense_map = {item["user_id"]: item["amount"] for item in member_expenses}

        # 가족 총 지출
        family_total = sum(expense_map.values())

        # 구성원별 실제 지출 리스트
        member_data = []
        for member in members:
            actual = expense_map.get(member.id, 0)
            member_data.append({
                "user_id": member.id,
                "nickname": member.nickname,
                "actual_expense": actual,
            })

        # 부담액 계산
        member_count = len(members)
        if ratio:
            # 비율 분할
            ratios = parse_ratio(ratio, member_count)
            shares = [int(family_total * r) for r in ratios]
            # 반올림 오차 보정: 마지막 구성원에게 나머지 할당
            diff = family_total - sum(shares)
            shares[-1] += diff
            split_method = f"ratio ({ratio})"
        else:
            # 균등 분할
            base = family_total // member_count
            remainder = family_total % member_count
            shares = [base] * member_count
            # 나머지를 앞에서부터 1씩 분배
            for i in range(remainder):
                shares[i] += 1
            split_method = "equal"

        # 정산 이체 계산
        transfers_data = calculate_settlement_transfers(member_data, shares)

        # 응답 구성
        member_settlements = []
        for i, md in enumerate(member_data):
            expense_ratio = (
                round(md["actual_expense"] / family_total * 100, 1)
                if family_total > 0
                else 0.0
            )
            member_settlements.append(
                MemberSettlement(
                    user_id=md["user_id"],
                    nickname=md["nickname"],
                    actual_expense=md["actual_expense"],
                    expense_ratio=expense_ratio,
                    share_amount=shares[i],
                    difference=md["actual_expense"] - shares[i],
                )
            )

        transfers = [
            SettlementTransfer(
                from_user_id=t["from_user_id"],
                from_nickname=t["from_nickname"],
                to_user_id=t["to_user_id"],
                to_nickname=t["to_nickname"],
                amount=t["amount"],
            )
            for t in transfers_data
        ]

        return SettlementResponse(
            year=year,
            month=month,
            family_total_expense=family_total,
            split_method=split_method,
            members=member_settlements,
            transfers=transfers,
        )
