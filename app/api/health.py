"""
헬스체크 엔드포인트 모듈.

애플리케이션 상태와 데이터베이스 연결 상태를 확인하는 API를 제공한다.
"""

import logging

from fastapi import APIRouter

from app.core.database import check_db_connection
from app.schemas.common import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    앱 상태 및 DB 연결 상태를 반환하는 헬스체크 엔드포인트.

    DB 연결 성공 시 "connected", 실패 시 "disconnected"를 반환한다.
    """
    # DB 연결 상태 확인
    db_connected = await check_db_connection()
    db_status = "connected" if db_connected else "disconnected"

    if not db_connected:
        logger.warning("헬스체크: 데이터베이스 연결 실패")

    return HealthResponse(
        status="healthy",
        database=db_status,
        version="0.1.0",
    )
