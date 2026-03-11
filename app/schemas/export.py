"""
데이터 내보내기(Export) 관련 Pydantic 스키마.

CSV/엑셀 내보내기 API에서 사용하는 필터 파라미터 모델을 정의한다.
"""

from datetime import date

from pydantic import BaseModel, model_validator


# ──────────────────────────────────────────────
# 필터 파라미터 스키마
# ──────────────────────────────────────────────


class ExportFilterParams(BaseModel):
    """내보내기 필터 파라미터."""

    start_date: date
    end_date: date
    category: str | None = None
    area: str | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "ExportFilterParams":
        """시작일이 종료일보다 이후이면 에러."""
        if self.start_date > self.end_date:
            raise ValueError("시작일이 종료일보다 이후일 수 없습니다")
        return self
