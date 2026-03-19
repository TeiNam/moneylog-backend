-- ============================================================
-- MoneyLog 데이터베이스 테이블 생성 스크립트
-- PostgreSQL 16+ 기준
-- 생성일: 2026-03-13
--
-- 규칙:
--   - FK 제약조건 없음 (논리적 FK만 COMMENT로 표현)
--   - PK는 UUID(gen_random_uuid()) 또는 BIGINT IDENTITY 사용
--   - 타임스탬프는 timestamptz 사용
--   - 로그성 테이블은 월별 RANGE 파티셔닝 적용
--   - 프로시저/트리거/이벤트/RULE 사용 금지
-- ============================================================

-- 스키마 생성
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS ledger;

-- ============================================================
-- auth 스키마
-- ============================================================

-- ------------------------------------------------------------
-- auth.users: 사용자 계정 정보
-- ------------------------------------------------------------
CREATE TABLE auth.users (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    email           varchar(255) NOT NULL,
    nickname        varchar(100) NOT NULL,
    password_hash   varchar(255),                          -- SSO 사용자는 null
    profile_image   varchar(500),
    auth_provider   varchar(20)  NOT NULL DEFAULT 'EMAIL', -- EMAIL, GOOGLE, APPLE, KAKAO, NAVER
    family_group_id uuid,                                  -- 논리적 FK → auth.family_groups.id
    role_in_group   varchar(20)  NOT NULL DEFAULT 'MEMBER',-- OWNER, MEMBER
    default_asset_id uuid,                                 -- 논리적 FK → ledger.assets.id
    email_verified  boolean      NOT NULL DEFAULT false,
    status          varchar(20)  NOT NULL DEFAULT 'ACTIVE',-- ACTIVE, DORMANT, WITHDRAWN
    created_at      timestamptz  NOT NULL DEFAULT now(),
    last_login_at   timestamptz,
    CONSTRAINT users_pk PRIMARY KEY (id)
);

CREATE UNIQUE INDEX uidx_users_email ON auth.users (email);

COMMENT ON TABLE  auth.users IS '사용자 계정 정보 테이블';
COMMENT ON COLUMN auth.users.family_group_id IS '논리적 FK → auth.family_groups.id';
COMMENT ON COLUMN auth.users.default_asset_id IS '논리적 FK → ledger.assets.id';
COMMENT ON COLUMN auth.users.auth_provider IS '인증 제공자: EMAIL, GOOGLE, APPLE, KAKAO, NAVER';
COMMENT ON COLUMN auth.users.role_in_group IS '그룹 내 역할: OWNER, MEMBER';
COMMENT ON COLUMN auth.users.status IS '계정 상태: ACTIVE, DORMANT, WITHDRAWN';

-- ------------------------------------------------------------
-- auth.email_verifications: 이메일 인증 코드
-- ------------------------------------------------------------
CREATE TABLE auth.email_verifications (
    id          uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id     uuid        NOT NULL,   -- 논리적 FK → auth.users.id
    code        varchar(6)  NOT NULL,   -- 6자리 숫자 인증 코드
    expires_at  timestamptz NOT NULL,
    attempts    int         NOT NULL DEFAULT 0,
    is_valid    boolean     NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT email_verifications_pk PRIMARY KEY (id)
);

COMMENT ON TABLE  auth.email_verifications IS '이메일 인증 코드 관리 테이블';
COMMENT ON COLUMN auth.email_verifications.user_id IS '논리적 FK → auth.users.id';

-- ------------------------------------------------------------
-- auth.family_groups: 가족 그룹
-- ------------------------------------------------------------
CREATE TABLE auth.family_groups (
    id                      uuid        NOT NULL DEFAULT gen_random_uuid(),
    name                    varchar(50) NOT NULL,
    invite_code             varchar(8)  NOT NULL,   -- 8자리 영숫자 초대 코드
    invite_code_expires_at  timestamptz NOT NULL,
    owner_id                uuid        NOT NULL,   -- 논리적 FK → auth.users.id (그룹장)
    created_at              timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT family_groups_pk PRIMARY KEY (id)
);

CREATE UNIQUE INDEX uidx_family_groups_invite_code ON auth.family_groups (invite_code);

COMMENT ON TABLE  auth.family_groups IS '가족 그룹 테이블';
COMMENT ON COLUMN auth.family_groups.owner_id IS '논리적 FK → auth.users.id (그룹장)';
COMMENT ON COLUMN auth.family_groups.invite_code IS '8자리 영숫자 초대 코드';

-- ============================================================
-- ledger 스키마
-- ============================================================

-- ------------------------------------------------------------
-- ledger.assets: 자산(결제수단)
-- ------------------------------------------------------------
CREATE TABLE ledger.assets (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    family_group_id uuid,                       -- 논리적 FK → auth.family_groups.id
    ownership       varchar(20) NOT NULL,       -- PERSONAL, SHARED
    name            varchar(100) NOT NULL,
    asset_type      varchar(20) NOT NULL,       -- BANK_ACCOUNT, CREDIT_CARD, DEBIT_CARD, CASH, INVESTMENT, OTHER
    institution     varchar(100),
    balance         bigint,
    memo            text,
    icon            varchar(50),
    color           varchar(7),                 -- #RRGGBB
    is_active       boolean     NOT NULL DEFAULT true,
    sort_order      int         NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz,
    CONSTRAINT assets_pk PRIMARY KEY (id)
);

CREATE INDEX idx_assets_user_id ON ledger.assets (user_id);
CREATE INDEX idx_assets_family_group_id ON ledger.assets (family_group_id);

COMMENT ON TABLE  ledger.assets IS '자산(결제수단) 테이블';
COMMENT ON COLUMN ledger.assets.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.assets.family_group_id IS '논리적 FK → auth.family_groups.id';
COMMENT ON COLUMN ledger.assets.ownership IS '소유권: PERSONAL, SHARED';
COMMENT ON COLUMN ledger.assets.asset_type IS '자산 유형: BANK_ACCOUNT, CREDIT_CARD, DEBIT_CARD, CASH, INVESTMENT, OTHER';

-- ------------------------------------------------------------
-- ledger.transactions: 수입/지출 거래 내역
-- ------------------------------------------------------------
CREATE TABLE ledger.transactions (
    id              bigint GENERATED ALWAYS AS IDENTITY,
    public_id       uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    family_group_id uuid,                       -- 논리적 FK → auth.family_groups.id
    date            date        NOT NULL,
    area            varchar(20) NOT NULL,       -- GENERAL, CAR, SUBSCRIPTION, EVENT
    type            varchar(20) NOT NULL,       -- INCOME, EXPENSE
    major_category  varchar(50) NOT NULL,
    minor_category  varchar(50) NOT NULL,
    description     varchar(200) NOT NULL,
    amount          int         NOT NULL,
    discount        int         NOT NULL DEFAULT 0,
    actual_amount   int         NOT NULL,       -- amount - discount
    asset_id        uuid,                       -- 논리적 FK → ledger.assets.id
    memo            text,
    source          varchar(20) NOT NULL,       -- MANUAL, AI_CHAT, RECEIPT_SCAN, SUBSCRIPTION_AUTO
    is_private      boolean     NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz,
    CONSTRAINT transactions_pk PRIMARY KEY (id)
);

CREATE UNIQUE INDEX uidx_transactions_public_id ON ledger.transactions (public_id);
CREATE INDEX idx_transactions_user_id_date ON ledger.transactions (user_id, date);
CREATE INDEX idx_transactions_family_group_id_date ON ledger.transactions (family_group_id, date);
CREATE INDEX idx_transactions_asset_id_date ON ledger.transactions (asset_id, date);
CREATE INDEX idx_transactions_area_date ON ledger.transactions (area, date);
CREATE INDEX idx_transactions_user_id_is_private ON ledger.transactions (user_id, is_private);
-- 공개 거래 조회 최적화를 위한 부분 인덱스
CREATE INDEX idx_transactions_user_id_date_not_private
    ON ledger.transactions (user_id, date)
    WHERE is_private = false;

COMMENT ON TABLE  ledger.transactions IS '수입/지출 거래 내역 테이블';
COMMENT ON COLUMN ledger.transactions.public_id IS '외부 노출용 UUID (API 식별자)';
COMMENT ON COLUMN ledger.transactions.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.transactions.family_group_id IS '논리적 FK → auth.family_groups.id';
COMMENT ON COLUMN ledger.transactions.asset_id IS '논리적 FK → ledger.assets.id';
COMMENT ON COLUMN ledger.transactions.area IS '거래 영역: GENERAL, CAR, SUBSCRIPTION, EVENT';
COMMENT ON COLUMN ledger.transactions.type IS '거래 유형: INCOME, EXPENSE';
COMMENT ON COLUMN ledger.transactions.source IS '입력 출처: MANUAL, AI_CHAT, RECEIPT_SCAN, SUBSCRIPTION_AUTO';
COMMENT ON COLUMN ledger.transactions.is_private IS '비밀 거래 여부 (기본값 false)';

-- ------------------------------------------------------------
-- ledger.car_expense_details: 차계부 비용 상세
-- ------------------------------------------------------------
CREATE TABLE ledger.car_expense_details (
    id                  uuid        NOT NULL DEFAULT gen_random_uuid(),
    transaction_id      bigint      NOT NULL,   -- 논리적 FK → ledger.transactions.id
    car_type            varchar(20) NOT NULL,   -- FUEL, MAINTENANCE, INSURANCE, TAX, TOLL, PARKING, WASH, INSTALLMENT, OTHER
    fuel_amount_liter   numeric,
    fuel_unit_price     int,
    odometer            int,
    station_name        varchar(100),
    CONSTRAINT car_expense_details_pk PRIMARY KEY (id)
);

COMMENT ON TABLE  ledger.car_expense_details IS '차계부 비용 상세 테이블';
COMMENT ON COLUMN ledger.car_expense_details.transaction_id IS '논리적 FK → ledger.transactions.id';
COMMENT ON COLUMN ledger.car_expense_details.car_type IS '차계부 비용 유형: FUEL, MAINTENANCE, INSURANCE, TAX, TOLL, PARKING, WASH, INSTALLMENT, OTHER';

-- ------------------------------------------------------------
-- ledger.ceremony_events: 경조사 이벤트 상세
-- ------------------------------------------------------------
CREATE TABLE ledger.ceremony_events (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    transaction_id  bigint      NOT NULL,       -- 논리적 FK → ledger.transactions.id
    direction       varchar(20) NOT NULL,       -- SENT, RECEIVED
    event_type      varchar(20) NOT NULL,       -- WEDDING, FUNERAL, FIRST_BIRTHDAY, BIRTHDAY, HOUSEWARMING, OPENING, HOLIDAY, OTHER
    person_name     varchar(50) NOT NULL,
    relationship    varchar(50) NOT NULL,
    venue           varchar(200),
    CONSTRAINT ceremony_events_pk PRIMARY KEY (id)
);

COMMENT ON TABLE  ledger.ceremony_events IS '경조사 이벤트 상세 테이블';
COMMENT ON COLUMN ledger.ceremony_events.transaction_id IS '논리적 FK → ledger.transactions.id';
COMMENT ON COLUMN ledger.ceremony_events.direction IS '경조사 방향: SENT, RECEIVED';
COMMENT ON COLUMN ledger.ceremony_events.event_type IS '이벤트 유형: WEDDING, FUNERAL, FIRST_BIRTHDAY, BIRTHDAY, HOUSEWARMING, OPENING, HOLIDAY, OTHER';

-- ------------------------------------------------------------
-- ledger.ceremony_persons: 경조사 인물 누적 기록
-- ------------------------------------------------------------
CREATE TABLE ledger.ceremony_persons (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    name            varchar(50) NOT NULL,
    relationship    varchar(50) NOT NULL,
    total_sent      int         NOT NULL DEFAULT 0,
    total_received  int         NOT NULL DEFAULT 0,
    event_count     int         NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz,
    CONSTRAINT ceremony_persons_pk PRIMARY KEY (id)
);

COMMENT ON TABLE  ledger.ceremony_persons IS '경조사 인물 누적 기록 테이블';
COMMENT ON COLUMN ledger.ceremony_persons.user_id IS '논리적 FK → auth.users.id';

-- ------------------------------------------------------------
-- ledger.category_configs: 카테고리 설정
-- ------------------------------------------------------------
CREATE TABLE ledger.category_configs (
    id                  uuid        NOT NULL DEFAULT gen_random_uuid(),
    owner_id            uuid        NOT NULL,       -- 논리적 FK → auth.users.id 또는 auth.family_groups.id
    owner_type          varchar(20) NOT NULL,       -- USER, FAMILY_GROUP
    area                varchar(20) NOT NULL,       -- GENERAL, CAR, SUBSCRIPTION, EVENT
    type                varchar(20) NOT NULL,       -- INCOME, EXPENSE
    major_category      varchar(50) NOT NULL,
    minor_categories    text[]      NOT NULL DEFAULT '{}',
    icon                varchar(50),
    color               varchar(7),                 -- #RRGGBB
    is_active           boolean     NOT NULL DEFAULT true,
    is_default          boolean     NOT NULL DEFAULT false,
    sort_order          int         NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz,
    CONSTRAINT category_configs_pk PRIMARY KEY (id)
);

CREATE INDEX idx_category_configs_owner
    ON ledger.category_configs (owner_id, owner_type, area, type);

COMMENT ON TABLE  ledger.category_configs IS '카테고리 설정 테이블';
COMMENT ON COLUMN ledger.category_configs.owner_id IS '논리적 FK → auth.users.id (owner_type=FAMILY_GROUP일 때 auth.family_groups.id)';
COMMENT ON COLUMN ledger.category_configs.owner_type IS '소유자 유형: USER, FAMILY_GROUP';
COMMENT ON COLUMN ledger.category_configs.area IS '거래 영역: GENERAL, CAR, SUBSCRIPTION, EVENT';
COMMENT ON COLUMN ledger.category_configs.type IS '거래 유형: INCOME, EXPENSE';
COMMENT ON COLUMN ledger.category_configs.minor_categories IS '소분류 카테고리 목록 (PostgreSQL 배열)';

-- ------------------------------------------------------------
-- ledger.budgets: 월별 카테고리별 예산
-- ------------------------------------------------------------
CREATE TABLE ledger.budgets (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    family_group_id uuid,                       -- 논리적 FK → auth.family_groups.id
    year            smallint    NOT NULL,
    month           smallint    NOT NULL,       -- 1~12
    category        varchar(50) NOT NULL,       -- 대분류 카테고리명
    budget_amount   int         NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz,
    CONSTRAINT budgets_pk PRIMARY KEY (id)
);

CREATE INDEX idx_budgets_user_id_year_month ON ledger.budgets (user_id, year, month);

COMMENT ON TABLE  ledger.budgets IS '월별 카테고리별 예산 테이블';
COMMENT ON COLUMN ledger.budgets.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.budgets.family_group_id IS '논리적 FK → auth.family_groups.id';

-- ------------------------------------------------------------
-- ledger.goals: 재무 목표
-- ------------------------------------------------------------
CREATE TABLE ledger.goals (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    family_group_id uuid,                       -- 논리적 FK → auth.family_groups.id
    type            varchar(20) NOT NULL,       -- MONTHLY_SAVING, SAVING_RATE, SPECIAL
    title           varchar(200) NOT NULL,
    target_amount   int         NOT NULL,
    current_amount  int         NOT NULL DEFAULT 0,
    start_date      date        NOT NULL,
    end_date        date        NOT NULL,
    status          varchar(20) NOT NULL,       -- ACTIVE, COMPLETED, FAILED
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz,
    CONSTRAINT goals_pk PRIMARY KEY (id)
);

CREATE INDEX idx_goals_user_id_status ON ledger.goals (user_id, status);

COMMENT ON TABLE  ledger.goals IS '재무 목표 테이블';
COMMENT ON COLUMN ledger.goals.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.goals.family_group_id IS '논리적 FK → auth.family_groups.id';
COMMENT ON COLUMN ledger.goals.type IS '목표 유형: MONTHLY_SAVING, SAVING_RATE, SPECIAL';
COMMENT ON COLUMN ledger.goals.status IS '목표 상태: ACTIVE, COMPLETED, FAILED';

-- ------------------------------------------------------------
-- ledger.subscriptions: 구독 관리
-- ------------------------------------------------------------
CREATE TABLE ledger.subscriptions (
    id                  uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id             uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    family_group_id     uuid,                       -- 논리적 FK → auth.family_groups.id
    service_name        varchar(100) NOT NULL,
    category            varchar(20) NOT NULL,       -- OTT, MUSIC, CLOUD, PRODUCTIVITY, AI, GAME, NEWS, OTHER
    amount              int         NOT NULL,
    cycle               varchar(20) NOT NULL,       -- MONTHLY, YEARLY, WEEKLY
    billing_day         int         NOT NULL,       -- 1~31
    asset_id            uuid,                       -- 논리적 FK → ledger.assets.id
    start_date          date        NOT NULL,
    end_date            date,
    status              varchar(20) NOT NULL,       -- ACTIVE, PAUSED, CANCELLED
    notify_before_days  int         NOT NULL DEFAULT 1,
    memo                text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz,
    CONSTRAINT subscriptions_pk PRIMARY KEY (id)
);

CREATE INDEX idx_subscriptions_user_id ON ledger.subscriptions (user_id);
CREATE INDEX idx_subscriptions_user_id_status ON ledger.subscriptions (user_id, status);

COMMENT ON TABLE  ledger.subscriptions IS '구독 관리 테이블';
COMMENT ON COLUMN ledger.subscriptions.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.subscriptions.family_group_id IS '논리적 FK → auth.family_groups.id';
COMMENT ON COLUMN ledger.subscriptions.asset_id IS '논리적 FK → ledger.assets.id';
COMMENT ON COLUMN ledger.subscriptions.category IS '구독 카테고리: OTT, MUSIC, CLOUD, PRODUCTIVITY, AI, GAME, NEWS, OTHER';
COMMENT ON COLUMN ledger.subscriptions.cycle IS '결제 주기: MONTHLY, YEARLY, WEEKLY';
COMMENT ON COLUMN ledger.subscriptions.status IS '구독 상태: ACTIVE, PAUSED, CANCELLED';

-- ------------------------------------------------------------
-- ledger.notifications: 알림
-- ------------------------------------------------------------
CREATE TABLE ledger.notifications (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    subscription_id uuid        NOT NULL,       -- 논리적 FK → ledger.subscriptions.id
    type            varchar(30) NOT NULL,       -- SUBSCRIPTION_PAYMENT
    title           varchar(100) NOT NULL,
    message         text        NOT NULL,
    is_read         boolean     NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT notifications_pk PRIMARY KEY (id)
);

CREATE INDEX idx_notifications_user_id_is_read ON ledger.notifications (user_id, is_read);

COMMENT ON TABLE  ledger.notifications IS '알림 테이블';
COMMENT ON COLUMN ledger.notifications.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.notifications.subscription_id IS '논리적 FK → ledger.subscriptions.id';
COMMENT ON COLUMN ledger.notifications.type IS '알림 유형: SUBSCRIPTION_PAYMENT';

-- ------------------------------------------------------------
-- ledger.transfers: 계좌 간 이체 내역
-- ------------------------------------------------------------
CREATE TABLE ledger.transfers (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    family_group_id uuid,                       -- 논리적 FK → auth.family_groups.id
    from_asset_id   uuid        NOT NULL,       -- 논리적 FK → ledger.assets.id (출금)
    to_asset_id     uuid        NOT NULL,       -- 논리적 FK → ledger.assets.id (입금)
    amount          int         NOT NULL,
    fee             int         NOT NULL DEFAULT 0,
    description     varchar(200),
    transfer_date   date        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz,
    CONSTRAINT transfers_pk PRIMARY KEY (id)
);

CREATE INDEX idx_transfers_user_id_date ON ledger.transfers (user_id, transfer_date);

COMMENT ON TABLE  ledger.transfers IS '계좌 간 이체 내역 테이블';
COMMENT ON COLUMN ledger.transfers.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.transfers.family_group_id IS '논리적 FK → auth.family_groups.id';
COMMENT ON COLUMN ledger.transfers.from_asset_id IS '논리적 FK → ledger.assets.id (출금 자산)';
COMMENT ON COLUMN ledger.transfers.to_asset_id IS '논리적 FK → ledger.assets.id (입금 자산)';

-- ------------------------------------------------------------
-- ledger.receipt_scans: 영수증 OCR 스캔
-- ------------------------------------------------------------
CREATE TABLE ledger.receipt_scans (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    image_url       varchar(500),
    raw_text        text,
    extracted_data  jsonb,                      -- 추출된 거래 데이터
    status          varchar(20) NOT NULL,       -- PENDING, COMPLETED, FAILED
    transaction_id  bigint,                     -- 논리적 FK → ledger.transactions.id
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz,
    CONSTRAINT receipt_scans_pk PRIMARY KEY (id)
);

CREATE INDEX idx_receipt_scans_user_id_created_at ON ledger.receipt_scans (user_id, created_at);

COMMENT ON TABLE  ledger.receipt_scans IS '영수증 OCR 스캔 테이블';
COMMENT ON COLUMN ledger.receipt_scans.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.receipt_scans.extracted_data IS '추출된 거래 데이터 (JSONB)';
COMMENT ON COLUMN ledger.receipt_scans.transaction_id IS '논리적 FK → ledger.transactions.id';
COMMENT ON COLUMN ledger.receipt_scans.status IS '스캔 상태: PENDING, COMPLETED, FAILED';

-- ------------------------------------------------------------
-- ledger.ai_feedbacks: AI 오분류 피드백
-- ------------------------------------------------------------
CREATE TABLE ledger.ai_feedbacks (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,       -- 논리적 FK → auth.users.id
    transaction_id  bigint      NOT NULL,       -- 논리적 FK → ledger.transactions.id
    feedback_type   varchar(30) NOT NULL,       -- CATEGORY_CORRECTION, AMOUNT_CORRECTION, DESCRIPTION_CORRECTION
    original_value  varchar(200) NOT NULL,
    corrected_value varchar(200) NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_feedbacks_pk PRIMARY KEY (id)
);

CREATE INDEX idx_ai_feedbacks_user_id_created_at ON ledger.ai_feedbacks (user_id, created_at);
CREATE INDEX idx_ai_feedbacks_transaction_id ON ledger.ai_feedbacks (transaction_id);

COMMENT ON TABLE  ledger.ai_feedbacks IS 'AI 오분류 피드백 테이블';
COMMENT ON COLUMN ledger.ai_feedbacks.user_id IS '논리적 FK → auth.users.id';
COMMENT ON COLUMN ledger.ai_feedbacks.transaction_id IS '논리적 FK → ledger.transactions.id';
COMMENT ON COLUMN ledger.ai_feedbacks.feedback_type IS '피드백 유형: CATEGORY_CORRECTION, AMOUNT_CORRECTION, DESCRIPTION_CORRECTION';

-- ============================================================
-- 파티션 테이블 (로그성 — 월별 RANGE 파티셔닝)
-- ============================================================

-- ------------------------------------------------------------
-- ledger.ai_chat_sessions: AI 채팅 세션 (파티션)
-- ------------------------------------------------------------
CREATE TABLE ledger.ai_chat_sessions (
    id          uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id     uuid        NOT NULL,           -- 논리적 FK → auth.users.id
    title       varchar(200),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz,
    CONSTRAINT ai_chat_sessions_pk PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_ai_chat_sessions_user_id_created_at
    ON ledger.ai_chat_sessions (user_id, created_at);

-- 기본 파티션 (범위 밖 데이터 수용)
CREATE TABLE ledger.ai_chat_sessions_default
    PARTITION OF ledger.ai_chat_sessions DEFAULT;

-- 월별 파티션 예시 (2026년)
CREATE TABLE ledger.ai_chat_sessions_2026_01
    PARTITION OF ledger.ai_chat_sessions
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE ledger.ai_chat_sessions_2026_02
    PARTITION OF ledger.ai_chat_sessions
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE ledger.ai_chat_sessions_2026_03
    PARTITION OF ledger.ai_chat_sessions
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE ledger.ai_chat_sessions_2026_04
    PARTITION OF ledger.ai_chat_sessions
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE ledger.ai_chat_sessions_2026_05
    PARTITION OF ledger.ai_chat_sessions
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE ledger.ai_chat_sessions_2026_06
    PARTITION OF ledger.ai_chat_sessions
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

COMMENT ON TABLE  ledger.ai_chat_sessions IS 'AI 채팅 세션 테이블 (월별 파티셔닝)';
COMMENT ON COLUMN ledger.ai_chat_sessions.user_id IS '논리적 FK → auth.users.id';

-- ------------------------------------------------------------
-- ledger.ai_chat_messages: AI 채팅 메시지 (파티션)
-- ------------------------------------------------------------
CREATE TABLE ledger.ai_chat_messages (
    id              bigint GENERATED ALWAYS AS IDENTITY,
    public_id       uuid        NOT NULL DEFAULT gen_random_uuid(),
    session_id      uuid        NOT NULL,       -- 논리적 FK → ledger.ai_chat_sessions.id
    role            varchar(20) NOT NULL,       -- USER, ASSISTANT
    content         text        NOT NULL,
    extracted_data  jsonb,                      -- AI가 추출한 거래 데이터
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_chat_messages_pk PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE UNIQUE INDEX uidx_ai_chat_messages_public_id
    ON ledger.ai_chat_messages (public_id);
CREATE INDEX idx_ai_chat_messages_session_id_created_at
    ON ledger.ai_chat_messages (session_id, created_at);

-- 기본 파티션 (범위 밖 데이터 수용)
CREATE TABLE ledger.ai_chat_messages_default
    PARTITION OF ledger.ai_chat_messages DEFAULT;

-- 월별 파티션 예시 (2026년)
CREATE TABLE ledger.ai_chat_messages_2026_01
    PARTITION OF ledger.ai_chat_messages
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE ledger.ai_chat_messages_2026_02
    PARTITION OF ledger.ai_chat_messages
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE ledger.ai_chat_messages_2026_03
    PARTITION OF ledger.ai_chat_messages
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE ledger.ai_chat_messages_2026_04
    PARTITION OF ledger.ai_chat_messages
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE ledger.ai_chat_messages_2026_05
    PARTITION OF ledger.ai_chat_messages
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE ledger.ai_chat_messages_2026_06
    PARTITION OF ledger.ai_chat_messages
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

COMMENT ON TABLE  ledger.ai_chat_messages IS 'AI 채팅 메시지 테이블 (월별 파티셔닝)';
COMMENT ON COLUMN ledger.ai_chat_messages.public_id IS '외부 노출용 UUID (API 식별자)';
COMMENT ON COLUMN ledger.ai_chat_messages.session_id IS '논리적 FK → ledger.ai_chat_sessions.id';
COMMENT ON COLUMN ledger.ai_chat_messages.role IS '메시지 역할: USER, ASSISTANT';
COMMENT ON COLUMN ledger.ai_chat_messages.extracted_data IS 'AI가 추출한 거래 데이터 (JSONB)';

-- ============================================================
-- 월별 파티션 자동 생성 참고
-- ============================================================
-- pg_partman 확장을 사용하거나, 아래와 같은 패턴으로 새 월 파티션을 추가합니다:
--
-- CREATE TABLE ledger.ai_chat_sessions_2026_07
--     PARTITION OF ledger.ai_chat_sessions
--     FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
--
-- CREATE TABLE ledger.ai_chat_messages_2026_07
--     PARTITION OF ledger.ai_chat_messages
--     FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
-- ============================================================
