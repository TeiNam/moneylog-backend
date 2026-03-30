-- 카드 결제 주기 및 청구할인 관리 마이그레이션
-- Revision: 0014
-- Revises: 0013
-- Create Date: 2026-03-30
--
-- 변경 사항:
-- 1. ledger.assets 테이블에 payment_day, billing_start_day 컬럼 추가
-- 2. ledger.billing_discounts 테이블 신규 생성

-- ============================================================
-- 1. ledger.assets 테이블에 결제 주기 컬럼 추가
-- ============================================================

-- 결제일 (1~31, 카드 유형만 사용)
ALTER TABLE ledger.assets
    ADD COLUMN payment_day INTEGER;

COMMENT ON COLUMN ledger.assets.payment_day
    IS '결제일 (1~31, 카드 유형만 사용)';

-- 사용 기준일 (1~31, 카드 유형만 사용)
ALTER TABLE ledger.assets
    ADD COLUMN billing_start_day INTEGER;

COMMENT ON COLUMN ledger.assets.billing_start_day
    IS '사용 기준일 (1~31, 카드 유형만 사용)';

-- ============================================================
-- 2. ledger.billing_discounts 테이블 생성
-- ============================================================

CREATE TABLE ledger.billing_discounts (
    id          UUID            NOT NULL DEFAULT gen_random_uuid(),
    asset_id    UUID            NOT NULL,   -- 논리적 FK → ledger.assets.id
    user_id     UUID            NOT NULL,   -- 논리적 FK → auth.users.id
    name        VARCHAR(100)    NOT NULL,   -- 할인명
    amount      INTEGER         NOT NULL,   -- 할인 금액 (0 이상)
    cycle_start DATE            NOT NULL,   -- 적용 결제 주기 시작일
    cycle_end   DATE            NOT NULL,   -- 적용 결제 주기 종료일
    memo        TEXT,                        -- 메모
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ,

    CONSTRAINT pk_billing_discounts PRIMARY KEY (id)
);

COMMENT ON TABLE ledger.billing_discounts
    IS '카드 청구할인 항목 테이블';

COMMENT ON COLUMN ledger.billing_discounts.asset_id
    IS '논리적 FK → ledger.assets.id';
COMMENT ON COLUMN ledger.billing_discounts.user_id
    IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.billing_discounts.name
    IS '할인명';
COMMENT ON COLUMN ledger.billing_discounts.amount
    IS '할인 금액 (0 이상)';
COMMENT ON COLUMN ledger.billing_discounts.cycle_start
    IS '적용 결제 주기 시작일';
COMMENT ON COLUMN ledger.billing_discounts.cycle_end
    IS '적용 결제 주기 종료일';

-- ============================================================
-- 3. 인덱스 생성
-- ============================================================

-- 자산별 청구할인 조회용
CREATE INDEX idx_billing_discounts_asset_id
    ON ledger.billing_discounts (asset_id);

-- 자산 + 결제 주기별 조회/집계용
CREATE INDEX idx_billing_discounts_cycle
    ON ledger.billing_discounts (asset_id, cycle_start, cycle_end);

-- ============================================================
-- 롤백 (필요 시 수동 실행)
-- ============================================================
-- DROP INDEX IF EXISTS ledger.idx_billing_discounts_cycle;
-- DROP INDEX IF EXISTS ledger.idx_billing_discounts_asset_id;
-- DROP TABLE IF EXISTS ledger.billing_discounts;
-- ALTER TABLE ledger.assets DROP COLUMN IF EXISTS billing_start_day;
-- ALTER TABLE ledger.assets DROP COLUMN IF EXISTS payment_day;
