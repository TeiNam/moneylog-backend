"""
영수증 서비스.

영수증 이미지 OCR 분석, 스캔 이력 관리, 거래 확정을 담당한다.
BedrockClient를 통해 Claude Vision 모델과 통신하며,
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
from app.models.enums import ScanStatus, TransactionSource
from app.models.receipt_scan import ReceiptScan
from app.models.user import User
from app.repositories.receipt_scan_repository import ReceiptScanRepository
from app.schemas.transaction import TransactionCreateRequest
from app.services.bedrock_client import BedrockError
from app.utils.date_utils import safe_parse_date

logger = logging.getLogger(__name__)


class ReceiptService:
    """영수증 이미지 OCR 분석, 스캔 이력 관리, 거래 확정 서비스."""

    def __init__(
        self,
        scan_repo: ReceiptScanRepository,
        feedback_repo,
        bedrock_client,
        transaction_service,
    ) -> None:
        self._scan_repo = scan_repo
        self._feedback_repo = feedback_repo
        self._bedrock_client = bedrock_client
        self._transaction_service = transaction_service

    # ──────────────────────────────────────────────
    # 영수증 스캔 (OCR)
    # ──────────────────────────────────────────────

    async def scan_receipt(
        self, user: User, image_bytes: bytes, content_type: str
    ) -> ReceiptScan:
        """영수증 이미지를 Bedrock Vision으로 분석하여 거래 데이터를 추출한다.

        - PENDING 상태로 스캔 레코드 생성
        - 사용자 피드백 기반 프롬프트 강화
        - Bedrock Vision에 이미지 전달
        - raw_text, extracted_data 저장
        - 성공 시 COMPLETED, 실패 시 FAILED로 상태 변경

        Raises:
            BedrockError: Bedrock API 호출 실패 시
        """
        # 1. PENDING 상태로 스캔 레코드 생성
        scan = await self._scan_repo.create({
            "user_id": user.id,
            "status": ScanStatus.PENDING.value,
        })

        try:
            # 2. 사용자 최근 피드백 조회 (프롬프트 강화)
            feedbacks = await self._feedback_repo.get_recent_by_user(
                user.id, limit=20
            )

            # 3. 시스템 프롬프트 구성
            system_prompt = self._build_receipt_prompt(feedbacks)

            # 4. Bedrock Vision API 호출
            ai_response = await self._bedrock_client.converse_with_image(
                system_prompt=system_prompt,
                image_bytes=image_bytes,
                content_type=content_type,
            )

            # 5. AI 응답 파싱
            raw_text, extracted_data = self._parse_receipt_response(ai_response)

            # 6. 스캔 레코드 갱신 (COMPLETED)
            scan = await self._scan_repo.update(scan.id, {
                "status": ScanStatus.COMPLETED.value,
                "raw_text": raw_text,
                "extracted_data": extracted_data,
            })

            logger.info("영수증 스캔 완료: scan_id=%s", scan.id)
            return scan

        except BedrockError:
            # Bedrock API 실패 시 FAILED로 상태 변경
            await self._scan_repo.update(scan.id, {
                "status": ScanStatus.FAILED.value,
            })
            raise

    # ──────────────────────────────────────────────
    # 스캔 이력 조회
    # ──────────────────────────────────────────────

    async def get_scans(
        self, user: User, status: str | None = None
    ) -> list[ReceiptScan]:
        """현재 사용자의 스캔 이력을 최신순으로 반환한다. status 필터 선택 적용."""
        return await self._scan_repo.get_list_by_user(user.id, status=status)

    async def get_scan_detail(self, user: User, scan_id: UUID) -> ReceiptScan:
        """스캔 상세 정보를 반환한다.

        Raises:
            NotFoundError: 스캔이 존재하지 않을 때
            ForbiddenError: 다른 사용자의 스캔일 때
        """
        scan = await self._scan_repo.get_by_id(scan_id)
        self._check_scan_permission(user, scan)
        return scan

    # ──────────────────────────────────────────────
    # 거래 확정
    # ──────────────────────────────────────────────

    async def confirm_transaction(
        self, user: User, scan_id: UUID, overrides: dict | None = None
    ):
        """OCR 추출 데이터를 확정하여 Transaction을 생성한다.

        - status가 COMPLETED가 아니면 BadRequestError
        - 이미 transaction_id가 설정되어 있으면 ConflictError (409)
        - overrides가 있으면 extracted_data 대신 수정된 데이터 사용
        - source를 RECEIPT_SCAN으로 설정
        - 생성 후 scan.transaction_id 갱신

        Raises:
            NotFoundError: 스캔이 존재하지 않을 때
            ForbiddenError: 다른 사용자의 스캔일 때
            BadRequestError: status가 COMPLETED가 아닐 때
            ConflictError: 이미 거래가 생성되었을 때
        """
        # 1. 스캔 조회 및 소유권 검증
        scan = await self._scan_repo.get_by_id(scan_id)
        self._check_scan_permission(user, scan)

        # 2. 상태 검증 (Enum 인스턴스 직접 비교)
        if scan.status != ScanStatus.COMPLETED:
            raise BadRequestError("완료되지 않은 스캔은 확정할 수 없습니다")

        # 3. 중복 확정 방지
        if scan.transaction_id is not None:
            raise ConflictError("이미 거래가 생성되었습니다")

        # 4. overrides 병합 (overrides가 우선)
        tx_data = dict(scan.extracted_data) if scan.extracted_data else {}
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
            source=TransactionSource.RECEIPT_SCAN,
        )

        # 6. 거래 생성
        transaction = await self._transaction_service.create(user, tx_request)

        # 7. 스캔에 transaction_id 갱신
        await self._scan_repo.update(scan_id, {
            "transaction_id": transaction.id,
        })

        return transaction

    # ──────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────

    def _build_receipt_prompt(self, feedbacks: list) -> str:
        """영수증 OCR용 시스템 프롬프트를 구성한다."""
        prompt_parts = [
            "당신은 영수증 분석 AI 어시스턴트입니다.",
            "영수증 이미지에서 텍스트를 추출하고 거래 데이터를 파싱해주세요.",
            "",
            "응답 형식:",
            "1. 먼저 영수증에서 읽은 원본 텍스트를 그대로 출력해주세요.",
            "2. 그 다음 추출된 거래 데이터를 ```json 블록 안에 JSON 형식으로 포함해주세요.",
            "",
            "추출할 필드: date, area, type, major_category, minor_category, "
            "description, amount, discount, actual_amount",
            "",
        ]

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

    def _parse_receipt_response(self, ai_response: str) -> tuple[str, dict | None]:
        """AI 응답에서 raw_text와 extracted_data를 파싱한다.

        AI 응답 형식:
        - 원본 텍스트 부분 (raw_text)
        - ```json 블록 안의 구조화된 데이터 (extracted_data)
        """
        extracted_data = None
        raw_text = ai_response

        # ```json 블록에서 JSON 추출 시도
        json_block_pattern = r"```json\s*([\s\S]*?)\s*```"
        match = re.search(json_block_pattern, ai_response)
        if match:
            try:
                extracted_data = json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
            # raw_text는 JSON 블록을 제외한 나머지 텍스트
            raw_text = ai_response[:match.start()].strip()
        else:
            # 원시 JSON 객체 추출 시도
            json_obj_pattern = r"\{[\s\S]*\}"
            match = re.search(json_obj_pattern, ai_response)
            if match:
                try:
                    extracted_data = json.loads(match.group(0))
                    raw_text = ai_response[:match.start()].strip()
                except (json.JSONDecodeError, ValueError):
                    pass

        # raw_text가 비어있으면 전체 응답을 사용
        if not raw_text:
            raw_text = ai_response

        return raw_text, extracted_data

    def _check_scan_permission(
        self, user: User, scan: ReceiptScan | None
    ) -> None:
        """사용자가 해당 스캔에 접근할 권한이 있는지 검증한다."""
        if scan is None:
            raise NotFoundError("스캔을 찾을 수 없습니다")
        if scan.user_id != user.id:
            raise ForbiddenError("접근 권한이 없습니다")
