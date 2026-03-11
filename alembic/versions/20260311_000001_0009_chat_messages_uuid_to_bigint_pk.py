"""ai_chat_messages 테이블 UUID→bigint PK 전환

기존 UUID PK를 bigint IDENTITY PK로 변경하고,
기존 UUID 값을 public_id 컬럼으로 보존한다.

ai_chat_messages에는 FK 참조하는 다른 테이블이 없으므로
FK 갱신 단계는 불필요하다.

단계:
1. public_id UUID 컬럼 추가 및 기존 id 값 복사
2. public_id를 NOT NULL로 설정 + gen_random_uuid() 기본값
3. 기존 UUID PK 제약조건 제거
4. 기존 UUID id 컬럼 삭제
5. 새 bigint IDENTITY id 컬럼 추가 (PK)
6. uidx_ai_chat_messages_public_id 유니크 인덱스 생성
7. public_id 컬럼 코멘트 추가

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op

# Alembic 리비전 식별자
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1단계: public_id UUID 컬럼 추가 ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        ADD COLUMN public_id UUID
        """
    )

    # ── 2단계: 기존 UUID id 값을 public_id로 복사 ──
    op.execute(
        """
        UPDATE ledger.ai_chat_messages
        SET public_id = id
        """
    )

    # ── 3단계: public_id를 NOT NULL로 설정 ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        ALTER COLUMN public_id SET NOT NULL
        """
    )

    # ── 4단계: public_id에 기본값 설정 (신규 행에 자동 UUID 생성) ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        ALTER COLUMN public_id SET DEFAULT gen_random_uuid()
        """
    )

    # ── 5단계: 기존 UUID PK 제약조건 제거 ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        DROP CONSTRAINT ai_chat_messages_pkey
        """
    )

    # ── 6단계: 기존 UUID id 컬럼 삭제 ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        DROP COLUMN id
        """
    )

    # ── 7단계: 새 bigint IDENTITY id 컬럼 추가 (PK) ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        ADD COLUMN id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
        """
    )

    # ── 8단계: public_id에 유니크 인덱스 생성 ──
    op.execute(
        """
        CREATE UNIQUE INDEX uidx_ai_chat_messages_public_id
        ON ledger.ai_chat_messages (public_id)
        """
    )

    # ── 9단계: public_id 컬럼에 코멘트 추가 ──
    op.execute(
        """
        COMMENT ON COLUMN ledger.ai_chat_messages.public_id
        IS '외부 노출용 UUID (API 식별자)'
        """
    )


def downgrade() -> None:
    # ── 롤백: bigint PK → UUID PK 복원 ──

    # 1. 유니크 인덱스 제거
    op.execute(
        """
        DROP INDEX IF EXISTS ledger.uidx_ai_chat_messages_public_id
        """
    )

    # 2. bigint PK 제약조건 및 컬럼 제거
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        DROP CONSTRAINT ai_chat_messages_pkey
        """
    )
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        DROP COLUMN id
        """
    )

    # 3. public_id를 다시 id로 복원 (UUID PK)
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        RENAME COLUMN public_id TO id
        """
    )

    # 4. UUID PK 제약조건 복원
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        ADD CONSTRAINT ai_chat_messages_pkey PRIMARY KEY (id)
        """
    )

    # 5. 기본값 제거 (원래 UUID PK는 애플리케이션에서 생성)
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        ALTER COLUMN id DROP DEFAULT
        """
    )
