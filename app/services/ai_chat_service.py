"""
AI 채팅 서비스.

세션 관리, 자연어 거래 파싱, 대화 컨텍스트 유지, 거래 확정을 담당한다.
BedrockClient를 통해 Claude 모델과 통신하며,
피드백 이력을 시스템 프롬프트에 반영하여 분류 정확도를 향상시킨다.
"""

import json
import logging
import re
from datetime import date
from uuid import UUID

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.enums import MessageRole, TransactionSource
from app.models.user import User
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.schemas.transaction import TransactionCreateRequest
from app.utils.date_utils import safe_parse_date

logger = logging.getLogger(__name__)


class AIChatService:
    """AI 채팅 세션 관리, 자연어 거래 파싱, 거래 확정 서비스."""

    def __init__(
        self,
        session_repo: ChatSessionRepository,
        message_repo: ChatMessageRepository,
        feedback_repo,
        bedrock_client,
        transaction_service,
        category_repo,
        asset_repo,
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._feedback_repo = feedback_repo
        self._bedrock_client = bedrock_client
        self._transaction_service = transaction_service
        self._category_repo = category_repo
        self._asset_repo = asset_repo

    # ──────────────────────────────────────────────
    # 세션 관리
    # ──────────────────────────────────────────────

    async def create_session(
        self, user: User, title: str | None = None
    ) -> ChatSession:
        """새 채팅 세션을 생성한다. user_id는 현재 사용자로 자동 설정."""
        data = {"user_id": user.id, "title": title}
        session = await self._session_repo.create(data)
        logger.info("채팅 세션 생성 완료: session_id=%s", session.id)
        return session

    async def get_sessions(self, user: User) -> list[ChatSession]:
        """현재 사용자의 세션 목록을 최신순으로 반환한다."""
        return await self._session_repo.get_list_by_user(user.id)

    async def get_session_detail(self, user: User, session_id: UUID) -> dict:
        """세션 정보와 메시지 목록을 시간순으로 반환한다.

        Raises:
            NotFoundError: 세션이 존재하지 않을 때
            ForbiddenError: 다른 사용자의 세션일 때
        """
        session = await self._session_repo.get_by_id(session_id)
        self._check_session_permission(user, session)

        messages = await self._message_repo.get_list_by_session(session_id)
        return {"session": session, "messages": messages}

    async def delete_session(self, user: User, session_id: UUID) -> None:
        """세션과 관련 메시지를 모두 삭제한다.

        Raises:
            NotFoundError: 세션이 존재하지 않을 때
            ForbiddenError: 다른 사용자의 세션일 때
        """
        session = await self._session_repo.get_by_id(session_id)
        self._check_session_permission(user, session)

        # 메시지 먼저 삭제 후 세션 삭제
        await self._message_repo.delete_by_session(session_id)
        await self._session_repo.delete(session_id)
        logger.info("채팅 세션 삭제 완료: session_id=%s", session_id)

    # ──────────────────────────────────────────────
    # 메시지 전송 및 AI 파싱
    # ──────────────────────────────────────────────

    async def send_message(
        self, user: User, session_id: UUID, content: str
    ) -> ChatMessage:
        """자연어 메시지를 Bedrock에 전달하고 AI 응답을 저장한다.

        Raises:
            NotFoundError: 세션이 존재하지 않을 때
            ForbiddenError: 다른 사용자의 세션일 때
            BedrockError: Bedrock API 호출 실패 시
        """
        # 1. 세션 소유권 검증
        session = await self._session_repo.get_by_id(session_id)
        self._check_session_permission(user, session)

        # 2. 최근 메시지 이력 조회 (컨텍스트)
        recent_messages = await self._message_repo.get_recent_by_session(
            session_id, limit=20
        )

        # 3. 사용자 최근 피드백 조회
        feedbacks = await self._feedback_repo.get_recent_by_user(
            user.id, limit=20
        )

        # 4. 사용자 카테고리/자산 목록 조회
        categories = await self._category_repo.get_list(
            owner_id=user.id, owner_type="USER"
        )
        assets = await self._asset_repo.get_list_by_user(user.id)

        # 5. 시스템 프롬프트 구성
        system_prompt = self._build_system_prompt(categories, assets, feedbacks)

        # 6. 사용자 메시지 저장
        user_message = await self._message_repo.create({
            "session_id": session_id,
            "role": MessageRole.USER.value,
            "content": content,
        })

        # 7. Bedrock 대화 메시지 구성
        bedrock_messages = []
        for msg in recent_messages:
            bedrock_messages.append({
                "role": "user" if msg.role == MessageRole.USER.value else "assistant",
                "content": [{"text": msg.content}],
            })
        # 현재 사용자 메시지 추가
        bedrock_messages.append({
            "role": "user",
            "content": [{"text": content}],
        })

        # 8. Bedrock API 호출
        ai_response = await self._bedrock_client.converse(
            system_prompt=system_prompt,
            messages=bedrock_messages,
        )

        # 9. AI 응답에서 extracted_data 파싱
        extracted_data = self._parse_extracted_data(ai_response)

        # 10. AI 응답 메시지 저장
        ai_message = await self._message_repo.create({
            "session_id": session_id,
            "role": MessageRole.ASSISTANT.value,
            "content": ai_response,
            "extracted_data": extracted_data,
        })

        return ai_message

    # ──────────────────────────────────────────────
    # 거래 확정
    # ──────────────────────────────────────────────

    async def confirm_transaction(
        self, user: User, message_id: UUID, overrides: dict | None = None
    ):
        """AI가 추출한 거래 데이터를 확정하여 Transaction을 생성한다.

        Raises:
            NotFoundError: 메시지가 존재하지 않을 때
            ForbiddenError: 다른 사용자의 메시지일 때
            BadRequestError: extracted_data가 없을 때
            ConflictError: 이미 거래가 생성되었을 때
        """
        # 1. 메시지 조회 및 세션 소유권 검증
        message = await self._message_repo.get_by_id(message_id)
        if message is None:
            raise NotFoundError("메시지를 찾을 수 없습니다")

        session = await self._session_repo.get_by_id(message.session_id)
        self._check_session_permission(user, session)

        # 2. extracted_data 검증
        if not message.extracted_data:
            raise BadRequestError("추출된 거래 데이터가 없습니다")

        # 3. 중복 확정 방지
        if message.extracted_data.get("confirmed_transaction_id"):
            raise ConflictError("이미 거래가 생성되었습니다")

        # 4. overrides 병합 (overrides가 우선)
        tx_data = dict(message.extracted_data)
        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    tx_data[key] = value

        # 5. TransactionCreateRequest 구성
        from app.models.enums import Area, TransactionType

        tx_request = TransactionCreateRequest(
            date=safe_parse_date(tx_data.get("date")),
            area=tx_data.get("area", Area.GENERAL.value),
            type=tx_data.get("type", TransactionType.EXPENSE.value),
            major_category=tx_data.get("major_category", "기타"),
            minor_category=tx_data.get("minor_category", ""),
            description=tx_data.get("description", ""),
            amount=tx_data.get("amount", 0),
            discount=tx_data.get("discount", 0),
            asset_id=tx_data.get("asset_id"),
            source=TransactionSource.AI_CHAT,
        )

        # 6. 거래 생성
        transaction = await self._transaction_service.create(user, tx_request)

        # 7. 메시지에 confirmed_transaction_id 저장
        updated_extracted = dict(message.extracted_data)
        updated_extracted["confirmed_transaction_id"] = str(transaction.id)
        await self._message_repo.update(message_id, {
            "extracted_data": updated_extracted,
        })

        return transaction

    # ──────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────

    def _build_system_prompt(
        self, categories: list, assets: list, feedbacks: list
    ) -> str:
        """시스템 프롬프트를 구성한다. 카테고리, 자산, 피드백 이력을 포함."""
        prompt_parts = [
            "당신은 가계부 AI 어시스턴트입니다.",
            "사용자의 자연어 입력에서 거래 데이터를 추출해주세요.",
            "추출된 데이터는 JSON 형식으로 ```json 블록 안에 포함해주세요.",
            "",
            "추출할 필드: date, area, type, major_category, minor_category, "
            "description, amount, discount, actual_amount, asset_id",
            "",
        ]

        # 카테고리 목록 추가
        if categories:
            prompt_parts.append("사용자의 카테고리 목록:")
            for cat in categories:
                prompt_parts.append(
                    f"  - {cat.major_category}/{cat.minor_category} "
                    f"(영역: {cat.area}, 유형: {cat.type})"
                )
            prompt_parts.append("")

        # 자산(결제수단) 목록 추가
        if assets:
            prompt_parts.append("사용자의 결제수단 목록:")
            for asset in assets:
                prompt_parts.append(
                    f"  - {asset.name} (ID: {asset.id}, 유형: {asset.asset_type})"
                )
            prompt_parts.append("")

        # 피드백 이력 추가 (프롬프트 강화)
        if feedbacks:
            prompt_parts.append("사용자의 이전 수정 이력 (참고하여 분류 정확도를 높여주세요):")
            for fb in feedbacks:
                prompt_parts.append(
                    f"  - 사용자가 [{fb.original_value}]를 "
                    f"[{fb.corrected_value}]로 수정 ({fb.feedback_type})"
                )
            prompt_parts.append("")

        return "\n".join(prompt_parts)

    def _parse_extracted_data(self, ai_response: str) -> dict | None:
        """AI 응답에서 거래 데이터(JSON)를 추출한다. 추출 실패 시 None 반환."""
        # ```json 블록에서 JSON 추출 시도
        json_block_pattern = r"```json\s*([\s\S]*?)\s*```"
        match = re.search(json_block_pattern, ai_response)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

        # 원시 JSON 객체 추출 시도
        json_obj_pattern = r"\{[\s\S]*\}"
        match = re.search(json_obj_pattern, ai_response)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def _check_session_permission(
        self, user: User, session: ChatSession | None
    ) -> None:
        """사용자가 해당 세션에 접근할 권한이 있는지 검증한다."""
        if session is None:
            raise NotFoundError("채팅 세션을 찾을 수 없습니다")
        if session.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")
