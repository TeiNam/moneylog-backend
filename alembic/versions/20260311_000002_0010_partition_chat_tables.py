"""ai_chat_messages, ai_chat_sessions 테이블 월별 파티셔닝 전환

비파티션 테이블을 월별 RANGE 파티션 테이블로 전환한다.
기존 데이터를 올바른 월별 파티션으로 이동하고,
향후 3개월분 파티션과 기본 파티션(default)을 미리 생성한다.

전환 전략:
1. 기존 테이블을 _old로 이름 변경
2. 새 파티션 테이블 생성 (원래 이름으로)
3. 기존 데이터의 월별 범위를 조회하여 해당 파티션 생성
4. 기존 데이터를 새 파티션 테이블로 이동
5. 기존 _old 테이블 삭제
6. 향후 3개월분 파티션 미리 생성 (2026-03 ~ 2026-06)
7. 기본 파티션(default) 생성으로 데이터 유실 방지

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op

# Alembic 리비전 식별자
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # ai_chat_messages 테이블 파티셔닝 전환
    # ============================================================

    # ── 1단계: 기존 테이블을 _old로 이름 변경 ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        RENAME TO ai_chat_messages_old
        """
    )

    # ── 2단계: 기존 인덱스도 _old 접미사로 이름 변경 (충돌 방지) ──
    op.execute(
        """
        ALTER INDEX IF EXISTS ledger.idx_chat_message_session_created
        RENAME TO idx_chat_message_session_created_old
        """
    )
    op.execute(
        """
        ALTER INDEX IF EXISTS ledger.uidx_ai_chat_messages_public_id
        RENAME TO uidx_ai_chat_messages_public_id_old
        """
    )

    # ── 3단계: 새 파티션 테이블 생성 (복합 PK: id + created_at) ──
    op.execute(
        """
        CREATE TABLE ledger.ai_chat_messages (
            id BIGINT GENERATED ALWAYS AS IDENTITY,
            public_id UUID NOT NULL DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            extracted_data JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )

    # ── 4단계: 테이블 코멘트 설정 ──
    op.execute(
        """
        COMMENT ON TABLE ledger.ai_chat_messages IS 'AI 채팅 메시지 테이블'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN ledger.ai_chat_messages.public_id
        IS '외부 노출용 UUID (API 식별자)'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN ledger.ai_chat_messages.session_id
        IS '논리적 FK → ledger.ai_chat_sessions.id'
        """
    )

    # ── 5단계: 기본 파티션 생성 (데이터 유실 방지) ──
    op.execute(
        """
        CREATE TABLE ledger.ai_chat_messages_default
        PARTITION OF ledger.ai_chat_messages DEFAULT
        """
    )

    # ── 6단계: 기존 데이터의 월별 범위를 조회하여 파티션 생성 후 데이터 이동 ──
    # PL/pgSQL 블록으로 동적 파티션 생성 및 데이터 이동 처리
    op.execute(
        """
        DO $$
        DECLARE
            rec RECORD;
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            -- 기존 데이터에서 존재하는 월별 범위 조회
            FOR rec IN
                SELECT DISTINCT
                    date_trunc('month', created_at)::date AS month_start
                FROM ledger.ai_chat_messages_old
                ORDER BY month_start
            LOOP
                start_date := rec.month_start;
                end_date := (rec.month_start + INTERVAL '1 month')::date;
                partition_name := 'ai_chat_messages_'
                    || to_char(rec.month_start, 'YYYY_MM');

                -- 월별 파티션 생성
                EXECUTE format(
                    'CREATE TABLE ledger.%I PARTITION OF ledger.ai_chat_messages
                     FOR VALUES FROM (%L) TO (%L)',
                    partition_name, start_date, end_date
                );
            END LOOP;
        END $$
        """
    )

    # ── 7단계: 기존 데이터를 새 파티션 테이블로 이동 ──
    # IDENTITY 컬럼에 기존 값을 삽입하기 위해 OVERRIDING SYSTEM VALUE 사용
    op.execute(
        """
        INSERT INTO ledger.ai_chat_messages
            (id, public_id, session_id, role, content, extracted_data, created_at)
        OVERRIDING SYSTEM VALUE
        SELECT id, public_id, session_id, role, content, extracted_data, created_at
        FROM ledger.ai_chat_messages_old
        """
    )

    # ── 8단계: IDENTITY 시퀀스를 기존 최대값 이후로 재설정 ──
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('ledger.ai_chat_messages', 'id'),
            COALESCE((SELECT MAX(id) FROM ledger.ai_chat_messages), 0) + 1,
            false
        )
        """
    )

    # ── 9단계: 인덱스 재생성 ──
    op.execute(
        """
        CREATE INDEX idx_chat_message_session_created
        ON ledger.ai_chat_messages (session_id, created_at)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uidx_ai_chat_messages_public_id
        ON ledger.ai_chat_messages (public_id)
        """
    )

    # ── 10단계: 기존 _old 테이블 삭제 ──
    op.execute(
        """
        DROP TABLE ledger.ai_chat_messages_old
        """
    )

    # ── 11단계: 향후 3개월분 파티션 미리 생성 (2026-03 ~ 2026-06) ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger.ai_chat_messages_2026_03
        PARTITION OF ledger.ai_chat_messages
        FOR VALUES FROM ('2026-03-01') TO ('2026-04-01')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger.ai_chat_messages_2026_04
        PARTITION OF ledger.ai_chat_messages
        FOR VALUES FROM ('2026-04-01') TO ('2026-05-01')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger.ai_chat_messages_2026_05
        PARTITION OF ledger.ai_chat_messages
        FOR VALUES FROM ('2026-05-01') TO ('2026-06-01')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger.ai_chat_messages_2026_06
        PARTITION OF ledger.ai_chat_messages
        FOR VALUES FROM ('2026-06-01') TO ('2026-07-01')
        """
    )

    # ============================================================
    # ai_chat_sessions 테이블 파티셔닝 전환
    # ============================================================

    # ── 1단계: 기존 테이블을 _old로 이름 변경 ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_sessions
        RENAME TO ai_chat_sessions_old
        """
    )

    # ── 2단계: 기존 인덱스도 _old 접미사로 이름 변경 (충돌 방지) ──
    op.execute(
        """
        ALTER INDEX IF EXISTS ledger.idx_chat_session_user_created
        RENAME TO idx_chat_session_user_created_old
        """
    )

    # ── 3단계: 새 파티션 테이블 생성 (복합 PK: id UUID + created_at) ──
    op.execute(
        """
        CREATE TABLE ledger.ai_chat_sessions (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            title VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )

    # ── 4단계: 테이블 코멘트 설정 ──
    op.execute(
        """
        COMMENT ON TABLE ledger.ai_chat_sessions IS 'AI 채팅 세션 테이블'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN ledger.ai_chat_sessions.user_id
        IS '논리적 FK → auth.users.id'
        """
    )

    # ── 5단계: 기본 파티션 생성 (데이터 유실 방지) ──
    op.execute(
        """
        CREATE TABLE ledger.ai_chat_sessions_default
        PARTITION OF ledger.ai_chat_sessions DEFAULT
        """
    )

    # ── 6단계: 기존 데이터의 월별 범위를 조회하여 파티션 생성 후 데이터 이동 ──
    op.execute(
        """
        DO $$
        DECLARE
            rec RECORD;
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            FOR rec IN
                SELECT DISTINCT
                    date_trunc('month', created_at)::date AS month_start
                FROM ledger.ai_chat_sessions_old
                ORDER BY month_start
            LOOP
                start_date := rec.month_start;
                end_date := (rec.month_start + INTERVAL '1 month')::date;
                partition_name := 'ai_chat_sessions_'
                    || to_char(rec.month_start, 'YYYY_MM');

                EXECUTE format(
                    'CREATE TABLE ledger.%I PARTITION OF ledger.ai_chat_sessions
                     FOR VALUES FROM (%L) TO (%L)',
                    partition_name, start_date, end_date
                );
            END LOOP;
        END $$
        """
    )

    # ── 7단계: 기존 데이터를 새 파티션 테이블로 이동 ──
    op.execute(
        """
        INSERT INTO ledger.ai_chat_sessions
            (id, user_id, title, created_at, updated_at)
        SELECT id, user_id, title, created_at, updated_at
        FROM ledger.ai_chat_sessions_old
        """
    )

    # ── 8단계: 인덱스 재생성 ──
    op.execute(
        """
        CREATE INDEX idx_chat_session_user_created
        ON ledger.ai_chat_sessions (user_id, created_at)
        """
    )

    # ── 9단계: 기존 _old 테이블 삭제 ──
    op.execute(
        """
        DROP TABLE ledger.ai_chat_sessions_old
        """
    )

    # ── 10단계: 향후 3개월분 파티션 미리 생성 (2026-03 ~ 2026-06) ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger.ai_chat_sessions_2026_03
        PARTITION OF ledger.ai_chat_sessions
        FOR VALUES FROM ('2026-03-01') TO ('2026-04-01')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger.ai_chat_sessions_2026_04
        PARTITION OF ledger.ai_chat_sessions
        FOR VALUES FROM ('2026-04-01') TO ('2026-05-01')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger.ai_chat_sessions_2026_05
        PARTITION OF ledger.ai_chat_sessions
        FOR VALUES FROM ('2026-05-01') TO ('2026-06-01')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger.ai_chat_sessions_2026_06
        PARTITION OF ledger.ai_chat_sessions
        FOR VALUES FROM ('2026-06-01') TO ('2026-07-01')
        """
    )


def downgrade() -> None:
    # ============================================================
    # ai_chat_sessions 테이블: 파티션 → 비파티션 복원
    # ============================================================

    # ── 1단계: 파티션 테이블을 _partitioned로 이름 변경 ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_sessions
        RENAME TO ai_chat_sessions_partitioned
        """
    )

    # ── 2단계: 기존 인덱스 이름 변경 (충돌 방지) ──
    op.execute(
        """
        ALTER INDEX IF EXISTS ledger.idx_chat_session_user_created
        RENAME TO idx_chat_session_user_created_part
        """
    )

    # ── 3단계: 비파티션 테이블 생성 (0009 이후 상태: UUID PK) ──
    op.execute(
        """
        CREATE TABLE ledger.ai_chat_sessions (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            title VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            PRIMARY KEY (id)
        )
        """
    )

    # ── 4단계: 테이블 코멘트 복원 ──
    op.execute(
        """
        COMMENT ON TABLE ledger.ai_chat_sessions IS 'AI 채팅 세션 테이블'
        """
    )

    # ── 5단계: 파티션 테이블에서 데이터 복원 ──
    op.execute(
        """
        INSERT INTO ledger.ai_chat_sessions
            (id, user_id, title, created_at, updated_at)
        SELECT id, user_id, title, created_at, updated_at
        FROM ledger.ai_chat_sessions_partitioned
        """
    )

    # ── 6단계: 인덱스 재생성 ──
    op.execute(
        """
        CREATE INDEX idx_chat_session_user_created
        ON ledger.ai_chat_sessions (user_id, created_at)
        """
    )

    # ── 7단계: 파티션 테이블 삭제 (자식 파티션 포함) ──
    op.execute(
        """
        DROP TABLE ledger.ai_chat_sessions_partitioned CASCADE
        """
    )

    # ============================================================
    # ai_chat_messages 테이블: 파티션 → 비파티션 복원
    # ============================================================

    # ── 1단계: 파티션 테이블을 _partitioned로 이름 변경 ──
    op.execute(
        """
        ALTER TABLE ledger.ai_chat_messages
        RENAME TO ai_chat_messages_partitioned
        """
    )

    # ── 2단계: 기존 인덱스 이름 변경 (충돌 방지) ──
    op.execute(
        """
        ALTER INDEX IF EXISTS ledger.idx_chat_message_session_created
        RENAME TO idx_chat_message_session_created_part
        """
    )
    op.execute(
        """
        ALTER INDEX IF EXISTS ledger.uidx_ai_chat_messages_public_id
        RENAME TO uidx_ai_chat_messages_public_id_part
        """
    )

    # ── 3단계: 비파티션 테이블 생성 (0009 이후 상태: bigint IDENTITY PK) ──
    op.execute(
        """
        CREATE TABLE ledger.ai_chat_messages (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            public_id UUID NOT NULL DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            extracted_data JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # ── 4단계: 테이블 코멘트 복원 ──
    op.execute(
        """
        COMMENT ON TABLE ledger.ai_chat_messages IS 'AI 채팅 메시지 테이블'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN ledger.ai_chat_messages.public_id
        IS '외부 노출용 UUID (API 식별자)'
        """
    )

    # ── 5단계: 파티션 테이블에서 데이터 복원 ──
    op.execute(
        """
        INSERT INTO ledger.ai_chat_messages
            (id, public_id, session_id, role, content, extracted_data, created_at)
        OVERRIDING SYSTEM VALUE
        SELECT id, public_id, session_id, role, content, extracted_data, created_at
        FROM ledger.ai_chat_messages_partitioned
        """
    )

    # ── 6단계: IDENTITY 시퀀스 재설정 ──
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('ledger.ai_chat_messages', 'id'),
            COALESCE((SELECT MAX(id) FROM ledger.ai_chat_messages), 0) + 1,
            false
        )
        """
    )

    # ── 7단계: 인덱스 재생성 ──
    op.execute(
        """
        CREATE INDEX idx_chat_message_session_created
        ON ledger.ai_chat_messages (session_id, created_at)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uidx_ai_chat_messages_public_id
        ON ledger.ai_chat_messages (public_id)
        """
    )

    # ── 8단계: 파티션 테이블 삭제 (자식 파티션 포함) ──
    op.execute(
        """
        DROP TABLE ledger.ai_chat_messages_partitioned CASCADE
        """
    )
