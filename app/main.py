"""
MoneyLog 백엔드 FastAPI 애플리케이션 엔트리포인트.

앱 인스턴스 생성, CORS 미들웨어, 전역 예외 핸들러, 라우터 등록을 담당한다.
"""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.assets import router as assets_router
from app.api.categories import router as categories_router
from app.api.ceremony_persons import router as ceremony_persons_router
from app.api.family import router as family_router
from app.api.health import router as health_router
from app.api.notifications import router as notifications_router
from app.api.subscriptions import router as subscriptions_router
from app.api.transactions import router as transactions_router
from app.api.budgets import router as budgets_router
from app.api.goals import router as goals_router
from app.api.stats import router as stats_router
from app.api.settlement import router as settlement_router
# Phase 6 라우터
from app.api.transfers import router as transfers_router
from app.api.export import router as export_router
# Phase 7 라우터
from app.api.ai_chat import router as ai_chat_router
from app.api.receipts import router as receipts_router
from app.api.ai_analysis import router as ai_analysis_router
from app.api.ai_feedbacks import router as ai_feedbacks_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# API 버전 프리픽스 라우터
api_v1_router = APIRouter(prefix="/api/v1")


def create_app() -> FastAPI:
    """FastAPI 앱 인스턴스를 생성하고 설정을 적용한다."""
    application = FastAPI(
        title="MoneyLog API",
        description="MoneyLog 가계부 앱 백엔드 API",
        version="0.1.0",
    )

    # CORS 미들웨어 설정 — 환경별 오리진 분기
    settings = get_settings()
    if settings.APP_ENV == "production":
        # 운영 환경: ALLOWED_ORIGINS에서 파싱한 도메인만 허용
        origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
    else:
        # 개발/스테이징 환경: 모든 오리진 허용
        origins = ["*"]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 전역 예외 핸들러 등록
    register_exception_handlers(application)

    # 헬스체크 라우터를 앱 루트에 직접 등록 (/health 경로)
    application.include_router(health_router)

    # API v1 하위 라우터 등록
    api_v1_router.include_router(auth_router)
    api_v1_router.include_router(transactions_router)
    api_v1_router.include_router(ceremony_persons_router)
    api_v1_router.include_router(categories_router)
    api_v1_router.include_router(assets_router)
    api_v1_router.include_router(family_router)
    api_v1_router.include_router(subscriptions_router)
    api_v1_router.include_router(notifications_router)
    api_v1_router.include_router(budgets_router)
    api_v1_router.include_router(goals_router)
    api_v1_router.include_router(stats_router)
    api_v1_router.include_router(settlement_router)
    # Phase 6 라우터
    api_v1_router.include_router(transfers_router)
    api_v1_router.include_router(export_router)
    # Phase 7 라우터
    api_v1_router.include_router(ai_chat_router)
    api_v1_router.include_router(receipts_router)
    api_v1_router.include_router(ai_analysis_router)
    api_v1_router.include_router(ai_feedbacks_router)

    # API v1 라우터 등록
    application.include_router(api_v1_router)

    logger.info("MoneyLog API 앱 초기화 완료")
    return application


app = create_app()
