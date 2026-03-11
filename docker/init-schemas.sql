-- MoneyLog 데이터베이스 초기 스키마 생성
-- auth: 회원/인증 관련 테이블
-- ledger: 자산/입출력 관련 테이블 (Phase 2 이후)
-- stats: 통계 관련 테이블 (Phase 3 이후)

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS ledger;
CREATE SCHEMA IF NOT EXISTS stats;
