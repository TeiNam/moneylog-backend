"""
데이터 내보내기(Export) 관련 HTTP 엔드포인트.

CSV 및 엑셀(xlsx) 형식으로 거래 내역을 내보내기한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.export import ExportFilterParams
from app.services.export_service import ExportService
from app.utils.timezone_utils import parse_date_param_to_date

router = APIRouter(prefix="/export", tags=["export"])


def _build_service(db: AsyncSession) -> ExportService:
    """DB 세션으로 ExportService 인스턴스를 생성한다."""
    return ExportService(
        transaction_repo=TransactionRepository(db),
        asset_repo=AssetRepository(db),
    )


# ──────────────────────────────────────────────
# CSV 내보내기
# ──────────────────────────────────────────────


@router.get(
    "/csv",
    summary="CSV 내보내기",
    response_class=StreamingResponse,
)
async def export_csv(
    start_date: str = Query(..., description="시작일 (YYYY-MM-DD 또는 ISO 8601, 필수)"),
    end_date: str = Query(..., description="종료일 (YYYY-MM-DD 또는 ISO 8601, 필수)"),
    category: str | None = Query(None, description="대분류 카테고리 필터"),
    area: str | None = Query(None, description="영역 필터"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """거래 내역을 CSV 파일로 내보내기한다.

    날짜 파라미터는 KST 기준으로 해석된다 (Requirements 4.2, 4.3).
    """
    # KST 기준 날짜 파싱
    parsed_start = parse_date_param_to_date(start_date)
    parsed_end = parse_date_param_to_date(end_date)

    # 날짜 범위 검증 (start_date <= end_date)
    ExportFilterParams(
        start_date=parsed_start,
        end_date=parsed_end,
        category=category,
        area=area,
    )

    service = _build_service(db)
    csv_buffer = await service.export_csv(
        user=current_user,
        start_date=parsed_start,
        end_date=parsed_end,
        category=category,
        area=area,
    )

    filename = f"moneylog_{parsed_start}_{parsed_end}.csv"
    return StreamingResponse(
        csv_buffer,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ──────────────────────────────────────────────
# 엑셀(xlsx) 내보내기
# ──────────────────────────────────────────────


@router.get(
    "/xlsx",
    summary="엑셀 내보내기",
    response_class=StreamingResponse,
)
async def export_xlsx(
    start_date: str = Query(..., description="시작일 (YYYY-MM-DD 또는 ISO 8601, 필수)"),
    end_date: str = Query(..., description="종료일 (YYYY-MM-DD 또는 ISO 8601, 필수)"),
    category: str | None = Query(None, description="대분류 카테고리 필터"),
    area: str | None = Query(None, description="영역 필터"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """거래 내역을 엑셀(xlsx) 파일로 내보내기한다.

    날짜 파라미터는 KST 기준으로 해석된다 (Requirements 4.2, 4.3).
    """
    # KST 기준 날짜 파싱
    parsed_start = parse_date_param_to_date(start_date)
    parsed_end = parse_date_param_to_date(end_date)

    # 날짜 범위 검증 (start_date <= end_date)
    ExportFilterParams(
        start_date=parsed_start,
        end_date=parsed_end,
        category=category,
        area=area,
    )

    service = _build_service(db)
    xlsx_buffer = await service.export_xlsx(
        user=current_user,
        start_date=parsed_start,
        end_date=parsed_end,
        category=category,
        area=area,
    )

    filename = f"moneylog_{parsed_start}_{parsed_end}.xlsx"
    return StreamingResponse(
        xlsx_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
