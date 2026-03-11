"""transactions 테이블 UUID→bigint PK 전환

기존 UUID PK를 bigint IDENTITY PK로 변경하고,
기존 UUID 값을 public_id 컬럼으로 보존한다.

단계:
1. public_id UUID 컬럼 추가 및 기존 id 값 복사
2. 기존 UUID PK 제약조건 제거
3. id 컬럼을 bigint IDENTITY로 교체
4. public_id에 유니크 인덱스 생성
5. car_expense_details, ceremony_events의 transaction_id는
   논리적 FK이므로 UUID 타입 그대로 유지 (public_id를 참조)

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op

# Alembic 리비전 식별자
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1단계: public_id UUID 컬럼 추가 ──
    op.execute(
        """
        ALTER TABLE ledger.transactions
        ADD COLUMN public_id UUID
        """
    )

    # ── 2단계: 기존 UUID id 값을 public_id로 복사 ──
    op.execute(
        """
        UPDATE ledger.transactions
        SET public_id = id
        """
    )

    # ── 3단계: public_id를 NOT NULL로 설정 ──
    op.execute(
        """
        ALTER TABLE ledger.transactions
        ALTER COLUMN public_id SET NOT NULL
        """
    )

    # ── 4단계: public_id에 기본값 설정 (신규 행에 자동 UUID 생성) ──
    op.execute(
        """
        ALTER TABLE ledger.transactions
        ALTER COLUMN public_id SET DEFAULT gen_random_uuid()
        """
    )

    # ── 5단계: car_expense_details.transaction_id의 기존 UUID 값을 보존 ──
    # 논리적 FK이므로 물리적 제약은 없지만, 참조 무결성을 위해
    # transaction_id가 이제 public_id를 참조하도록 애플리케이션 레벨에서 처리한다.
    # DB 컬럼 타입(UUID)은 변경하지 않는다.

    # ── 6단계: 기존 UUID PK 제약조건 제거 ──
    op.execute(
        """
        ALTER TABLE ledger.transactions
        DROP CONSTRAINT transactions_pkey
        """
    )

    # ── 7단계: 기존 UUID id 컬럼 삭제 ──
    op.execute(
        """
        ALTER TABLE ledger.transactions
        DROP COLUMN id
        """
    )

    # ── 8단계: 새 bigint IDENTITY id 컬럼 추가 (PK) ──
    op.execute(
        """
        ALTER TABLE ledger.transactions
        ADD COLUMN id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
        """
    )

    # ── 9단계: public_id에 유니크 인덱스 생성 ──
    op.execute(
        """
        CREATE UNIQUE INDEX uidx_transactions_public_id
        ON ledger.transactions (public_id)
        """
    )

    # ── 10단계: public_id 컬럼에 코멘트 추가 ──
    op.execute(
        """
        COMMENT ON COLUMN ledger.transactions.public_id
        IS '외부 노출용 UUID (API 식별자)'
        """
    )


def downgrade() -> None:
    # ── 롤백: bigint PK → UUID PK 복원 ──

    # 1. 유니크 인덱스 제거
    op.execute(
        """
        DROP INDEX IF EXISTS ledger.uidx_transactions_public_id
        """
    )

    # 2. bigint PK 제약조건 및 컬럼 제거
    op.execute(
        """
        ALTER TABLE ledger.transactions
        DROP CONSTRAINT transactions_pkey
        """
    )
    op.execute(
        """
        ALTER TABLE ledger.transactions
        DROP COLUMN id
        """
    )

    # 3. public_id를 다시 id로 복원 (UUID PK)
    op.execute(
        """
        ALTER TABLE ledger.transactions
        RENAME COLUMN public_id TO id
        """
    )

    # 4. UUID PK 제약조건 복원
    op.execute(
        """
        ALTER TABLE ledger.transactions
        ADD CONSTRAINT transactions_pkey PRIMARY KEY (id)
        """
    )

    # 5. 기본값 제거 (원래 UUID PK는 애플리케이션에서 생성)
    op.execute(
        """
        ALTER TABLE ledger.transactions
        ALTER COLUMN id DROP DEFAULT
        """
    )
