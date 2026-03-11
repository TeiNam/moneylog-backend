"""
데이터 내보내기(Export) 서비스.

거래 내역을 CSV/엑셀(xlsx) 형식으로 변환하는 서비스.
순수 변환 함수(transactions_to_csv_bytes, transactions_to_xlsx_bytes, _transaction_to_row)는
모듈 레벨에 정의하여 DB 없이 독립 테스트가 가능하다.
"""

import csv
import logging
from datetime import date
from io import BytesIO, TextIOWrapper
from uuid import UUID

from openpyxl import Workbook

from sqlalchemy import Row

from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.transaction_repository import TransactionRepository

logger = logging.getLogger(__name__)

# 내보내기 CSV/엑셀 헤더 (한글)
EXPORT_HEADERS = [
    "날짜",
    "영역",
    "유형",
    "대분류",
    "소분류",
    "설명",
    "금액",
    "할인",
    "실지출",
    "결제수단",
    "메모",
]


def _transaction_to_row(tx: Row, asset_map: dict[UUID, str]) -> list:
    """거래 Row를 내보내기 행으로 변환한다.

    Args:
        tx: 거래 Row 객체 (속성 접근 지원)
        asset_map: asset_id → 자산명 매핑

    Returns:
        헤더 순서에 맞는 값 리스트
    """
    return [
        tx.date.isoformat(),
        tx.area,
        tx.type,
        tx.major_category,
        tx.minor_category,
        tx.description,
        tx.amount,
        tx.discount,
        tx.actual_amount,
        asset_map.get(tx.asset_id, "") if tx.asset_id else "",
        tx.memo or "",
    ]


def transactions_to_csv_bytes(
    transactions: list[Row], asset_map: dict[UUID, str]
) -> BytesIO:
    """거래 목록을 CSV BytesIO로 변환한다.

    Args:
        transactions: 거래 Row 목록
        asset_map: asset_id → 자산명 매핑

    Returns:
        UTF-8 BOM이 포함된 CSV BytesIO
    """
    buffer = BytesIO()
    # UTF-8 BOM 추가 (엑셀에서 한글 인코딩 지원)
    buffer.write(b"\xef\xbb\xbf")
    wrapper = TextIOWrapper(buffer, encoding="utf-8", newline="")
    writer = csv.writer(wrapper)
    writer.writerow(EXPORT_HEADERS)
    for tx in transactions:
        writer.writerow(_transaction_to_row(tx, asset_map))
    wrapper.flush()
    wrapper.detach()
    buffer.seek(0)
    return buffer


def transactions_to_xlsx_bytes(
    transactions: list[Row], asset_map: dict[UUID, str]
) -> BytesIO:
    """거래 목록을 엑셀(xlsx) BytesIO로 변환한다.

    Args:
        transactions: 거래 Row 목록
        asset_map: asset_id → 자산명 매핑

    Returns:
        xlsx BytesIO
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "거래내역"
    ws.append(EXPORT_HEADERS)
    for tx in transactions:
        ws.append(_transaction_to_row(tx, asset_map))
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


class ExportService:
    """거래 내역을 CSV/엑셀 형식으로 변환하는 서비스."""

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        asset_repo: AssetRepository,
    ) -> None:
        self._transaction_repo = transaction_repo
        self._asset_repo = asset_repo

    async def export_csv(
        self,
        user: User,
        start_date: date,
        end_date: date,
        category: str | None = None,
        area: str | None = None,
    ) -> BytesIO:
        """거래 내역을 CSV 형식으로 변환하여 BytesIO로 반환한다.

        - UTF-8 BOM 포함
        - 헤더: 날짜, 영역, 유형, 대분류, 소분류, 설명, 금액, 할인, 실지출, 결제수단, 메모
        - 비밀 거래(is_private=true) 포함 (본인 데이터)

        Args:
            user: 현재 인증된 사용자
            start_date: 시작일
            end_date: 종료일
            category: 대분류 카테고리 필터 (선택)
            area: 영역 필터 (선택)

        Returns:
            UTF-8 BOM이 포함된 CSV BytesIO
        """
        transactions = await self._transaction_repo.get_list_for_export(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            category=category,
            area=area,
        )
        asset_map = await self._build_asset_map(transactions)
        logger.info(
            "CSV 내보내기 완료: user_id=%s, 거래 수=%d",
            user.id,
            len(transactions),
        )
        return transactions_to_csv_bytes(transactions, asset_map)

    async def export_xlsx(
        self,
        user: User,
        start_date: date,
        end_date: date,
        category: str | None = None,
        area: str | None = None,
    ) -> BytesIO:
        """거래 내역을 엑셀(xlsx) 형식으로 변환하여 BytesIO로 반환한다.

        - 시트명: "거래내역"
        - 헤더: 날짜, 영역, 유형, 대분류, 소분류, 설명, 금액, 할인, 실지출, 결제수단, 메모

        Args:
            user: 현재 인증된 사용자
            start_date: 시작일
            end_date: 종료일
            category: 대분류 카테고리 필터 (선택)
            area: 영역 필터 (선택)

        Returns:
            xlsx BytesIO
        """
        transactions = await self._transaction_repo.get_list_for_export(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            category=category,
            area=area,
        )
        asset_map = await self._build_asset_map(transactions)
        logger.info(
            "엑셀 내보내기 완료: user_id=%s, 거래 수=%d",
            user.id,
            len(transactions),
        )
        return transactions_to_xlsx_bytes(transactions, asset_map)

    async def _build_asset_map(
        self, transactions: list[Row]
    ) -> dict[UUID, str]:
        """거래 목록에서 사용된 asset_id들의 자산명 매핑을 구축한다.

        Args:
            transactions: 거래 Row 목록

        Returns:
            asset_id → 자산명 딕셔너리
        """
        # 고유한 asset_id 수집
        asset_ids: set[UUID] = set()
        for tx in transactions:
            if tx.asset_id is not None:
                asset_ids.add(tx.asset_id)

        # 자산명 조회
        asset_map: dict[UUID, str] = {}
        for asset_id in asset_ids:
            asset = await self._asset_repo.get_by_id(asset_id)
            if asset is not None:
                asset_map[asset_id] = asset.name

        return asset_map
