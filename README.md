# MoneyLog Backend

![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-336791.svg)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://qr.kakaopay.com/Ej74xpc815dc06149)

## 개요

MoneyLog는 개인 및 가족 단위 가계부 관리를 위한 백엔드 API 서버입니다.
일반 거래, 차계부, 경조사, 구독 관리를 하나의 앱에서 처리하며,
AI 기반 자연어 거래 입력과 영수증 OCR 기능을 제공합니다.

## 주요 기능

- 거래 관리 (수입/지출, 차계부, 경조사)
- 자산(결제수단) 및 이체 관리
- 카테고리 커스터마이징
- 가족 그룹 공유 가계부 및 정산
- 구독 관리 및 자동 결제 배치
- 예산 설정 및 실적 비교
- 저축 목표 관리
- 주간/월간/연간 통계
- AI 채팅 기반 자연어 거래 입력 (Amazon Bedrock)
- 영수증 OCR 스캔 및 거래 자동 추출
- AI 지출 분석 리포트 및 절약 제안
- CSV/엑셀 내보내기
- 비밀 거래 모드 (가족 공유 시 특정 거래 숨김)

## 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.12+ |
| 프레임워크 | FastAPI 0.116 |
| ORM | SQLAlchemy 2.0 (async) |
| DB | PostgreSQL 17 + asyncpg |
| 마이그레이션 | Alembic |
| 인증 | JWT (python-jose, HS256) |
| AI | Amazon Bedrock (Claude) |
| 검증 | Pydantic 2.11 |
| 테스트 | pytest + Hypothesis (PBT) |
| 컨테이너 | Docker + Docker Compose |


## 프로젝트 구조

```
moneylog-backend/
├── app/
│   ├── api/            # API 라우터 (엔드포인트 정의)
│   ├── core/           # 설정, DB, 보안, 예외 처리
│   ├── models/         # SQLAlchemy ORM 모델
│   ├── repositories/   # 데이터 접근 계층
│   ├── schemas/        # Pydantic 요청/응답 스키마
│   ├── services/       # 비즈니스 로직 계층
│   ├── utils/          # 유틸리티 함수
│   └── main.py         # FastAPI 앱 엔트리포인트
├── alembic/            # DB 마이그레이션
├── tests/              # 테스트 코드
├── docker/             # Docker 초기화 스크립트
├── scripts/            # 운영 스크립트
├── docs/               # API 문서
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## 시작하기

### 사전 요구사항

- Python 3.12+
- PostgreSQL 17
- (선택) Docker & Docker Compose

### 로컬 설치

```bash
# 저장소 클론
git clone <repository-url>
cd moneylog-backend

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -e ".[dev]"

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 DATABASE_URL, JWT_SECRET_KEY 등 설정

# DB 마이그레이션 실행
alembic upgrade head

# 서버 실행
uvicorn app.main:app --reload
```

### Docker로 실행

```bash
# 환경 변수 설정
cp .env.example .env

# Docker Compose로 DB + API 서버 실행
docker compose up -d

# 마이그레이션 실행 (최초 1회)
docker compose exec api alembic upgrade head
```

서버가 실행되면 다음 URL에서 확인할 수 있습니다:
- API 서버: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 헬스체크: http://localhost:8000/health

## 환경 변수

| 변수 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| DATABASE_URL | Y | - | PostgreSQL 비동기 연결 URL |
| JWT_SECRET_KEY | Y | - | JWT 서명 시크릿 키 |
| JWT_ALGORITHM | N | HS256 | JWT 알고리즘 |
| ACCESS_TOKEN_EXPIRE_MINUTES | N | 30 | 액세스 토큰 만료 시간(분) |
| REFRESH_TOKEN_EXPIRE_DAYS | N | 7 | 리프레시 토큰 만료 시간(일) |
| APP_ENV | N | development | 환경 (development/staging/production) |
| ALLOWED_ORIGINS | N | * | CORS 허용 오리진 (쉼표 구분) |
| BATCH_API_KEY | N | - | 구독 배치 API 인증 키 |
| BEDROCK_MODEL_ID | N | anthropic.claude-3-5-sonnet-... | Bedrock 모델 ID |
| BEDROCK_REGION | N | us-east-1 | Bedrock 리전 |
| AWS_SECRET_NAME | N | - | Secrets Manager 시크릿 이름 (운영 환경) |

## API 문서

프론트엔드 개발을 위한 상세 API 레퍼런스는 [`docs/API.md`](docs/API.md)를 참고하세요.

모든 API는 `/api/v1` 프리픽스를 사용하며 (헬스체크 제외), JWT Bearer 토큰 인증이 필요합니다.

## 테스트

```bash
# 전체 테스트 실행
pytest

# 특정 테스트 파일 실행
pytest tests/test_transaction_service.py

# 커버리지 포함
pytest --cov=app
```

## DB 스키마

두 개의 PostgreSQL 스키마를 사용합니다:

- `auth` — 사용자, 이메일 인증, 가족 그룹
- `ledger` — 거래, 자산, 이체, 구독, 예산, 목표, AI 채팅, 영수증, 알림 등

## 라이선스

이 프로젝트는 개인 프로젝트입니다.
