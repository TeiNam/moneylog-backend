"""
AI 채팅(Chat) 관련 HTTP 엔드포인트.

채팅 세션 생성, 목록 조회, 상세 조회, 삭제,
자연어 메시지 전송, 추출된 거래 확정을 제공한다.
모든 엔드포인트는 인증된 사용자만 접근 가능하다.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.asset_repository import AssetRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.ceremony_person_repository import CeremonyPersonRepository
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.ai_feedback_repository import AIFeedbackRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.ai_chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    TransactionConfirmRequest,
)
from app.schemas.transaction import TransactionResponse
from app.services.ai_chat_service import AIChatService
from app.services.bedrock_client import BedrockClient, BedrockError
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/ai/chat", tags=["ai-chat"])


def _build_service(db: AsyncSession) -> AIChatService:
    """DB 세션으로 AIChatService 인스턴스를 생성한다."""
    return AIChatService(
        session_repo=ChatSessionRepository(db),
        message_repo=ChatMessageRepository(db),
        feedback_repo=AIFeedbackRepository(db),
        bedrock_client=BedrockClient(),
        transaction_service=TransactionService(
            TransactionRepository(db),
            CeremonyPersonRepository(db),
        ),
        category_repo=CategoryRepository(db),
        asset_repo=AssetRepository(db),
    )


# ──────────────────────────────────────────────
# 채팅 세션 생성
# ──────────────────────────────────────────────


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="채팅 세션 생성",
)
async def create_session(
    body: ChatSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """새로운 AI 채팅 세션을 생성한다."""
    service = _build_service(db)
    session = await service.create_session(current_user, body.title)
    await db.commit()
    return ChatSessionResponse.model_validate(session)


# ──────────────────────────────────────────────
# 채팅 세션 목록 조회
# ──────────────────────────────────────────────


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="채팅 세션 목록 조회",
)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionResponse]:
    """현재 사용자의 채팅 세션 목록을 최신순으로 조회한다."""
    service = _build_service(db)
    sessions = await service.get_sessions(current_user)
    return [ChatSessionResponse.model_validate(s) for s in sessions]


# ──────────────────────────────────────────────
# 채팅 세션 상세 조회
# ──────────────────────────────────────────────


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    summary="세션 상세(메시지 목록) 조회",
)
async def get_session_detail(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetailResponse:
    """세션 정보와 메시지 목록을 시간순으로 조회한다."""
    service = _build_service(db)
    detail = await service.get_session_detail(current_user, session_id)
    return ChatSessionDetailResponse(
        session=ChatSessionResponse.model_validate(detail["session"]),
        messages=[
            ChatMessageResponse.model_validate(m) for m in detail["messages"]
        ],
    )


# ──────────────────────────────────────────────
# 채팅 세션 삭제
# ──────────────────────────────────────────────


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="세션 삭제",
)
async def delete_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """세션과 관련 메시지를 모두 삭제한다."""
    service = _build_service(db)
    await service.delete_session(current_user, session_id)
    await db.commit()


# ──────────────────────────────────────────────
# 자연어 메시지 전송
# ──────────────────────────────────────────────


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="자연어 메시지 전송",
)
async def send_message(
    session_id: UUID,
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse | JSONResponse:
    """자연어 메시지를 전송하고 AI 응답을 반환한다."""
    service = _build_service(db)
    try:
        message = await service.send_message(
            current_user, session_id, body.content
        )
        await db.commit()
        return ChatMessageResponse.model_validate(message)
    except BedrockError as e:
        return JSONResponse(status_code=502, content={"detail": e.detail})


# ──────────────────────────────────────────────
# 추출된 거래 확정
# ──────────────────────────────────────────────


@router.post(
    "/messages/{message_id}/confirm",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="추출된 거래 확정",
)
async def confirm_transaction(
    message_id: UUID,
    body: TransactionConfirmRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    """AI가 추출한 거래 데이터를 확정하여 Transaction을 생성한다."""
    service = _build_service(db)
    overrides = (
        body.overrides.model_dump(exclude_none=True)
        if body and body.overrides
        else None
    )
    transaction = await service.confirm_transaction(
        current_user, message_id, overrides
    )
    await db.commit()
    return TransactionResponse.model_validate(transaction)
