# MoneyLog API 레퍼런스

> Base URL: `/api/v1`  
> 인증: `Authorization: Bearer <access_token>` (🔒 표시 엔드포인트)  
> 콘텐츠 타입: `application/json`

---

## 목차

1. [인증 (Auth)](#1-인증-auth)
2. [거래 (Transactions)](#2-거래-transactions)
3. [카테고리 (Categories)](#3-카테고리-categories)
4. [자산 (Assets)](#4-자산-assets)
5. [가족 그룹 (Family)](#5-가족-그룹-family)
6. [구독 (Subscriptions)](#6-구독-subscriptions)
7. [예산 (Budgets)](#7-예산-budgets)
8. [목표 (Goals)](#8-목표-goals)
9. [통계 (Stats)](#9-통계-stats)
10. [정산 (Settlement)](#10-정산-settlement)
11. [이체 (Transfers)](#11-이체-transfers)
12. [데이터 내보내기 (Export)](#12-데이터-내보내기-export)
13. [AI 채팅 (AI Chat)](#13-ai-채팅-ai-chat)
14. [영수증 OCR (Receipts)](#14-영수증-ocr-receipts)
15. [AI 분석 (AI Analysis)](#15-ai-분석-ai-analysis)
16. [AI 피드백 (AI Feedbacks)](#16-ai-피드백-ai-feedbacks)
17. [알림 (Notifications)](#17-알림-notifications)
18. [경조사 인물 (Ceremony Persons)](#18-경조사-인물-ceremony-persons)
19. [헬스체크 (Health)](#19-헬스체크-health)
20. [Enum 타입 정의](#20-enum-타입-정의)

---

## 공통 에러 응답

```json
{ "detail": "에러 메시지" }
```

| 상태 코드 | 설명 |
|-----------|------|
| 400 | 잘못된 요청 (유효성 검증 실패) |
| 401 | 인증 실패 (토큰 없음/만료) |
| 403 | 권한 없음 |
| 404 | 리소스 없음 |
| 409 | 충돌 (중복 데이터) |
| 422 | 요청 본문 파싱 실패 |
| 502 | AI 서비스 오류 (Bedrock) |


---

## 1. 인증 (Auth)

### POST `/auth/register` — 회원가입

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password1",
  "nickname": "홍길동"
}
```
- `password`: 8자 이상, 영문 1개 + 숫자 1개 이상 포함
- `nickname`: 1~100자

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "nickname": "홍길동",
  "auth_provider": "email",
  "email_verified": false,
  "status": "active",
  "created_at": "2026-01-01T00:00:00"
}
```

### POST `/auth/login` — 로그인

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password1"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### POST `/auth/verify-email` — 이메일 인증

**Request Body:**
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```
- `code`: 6자리 숫자

**Response:** `200 OK`
```json
{ "message": "이메일 인증이 완료되었습니다" }
```

### POST `/auth/resend-verification` — 인증 코드 재발송

**Request Body:**
```json
{ "email": "user@example.com" }
```

**Response:** `200 OK`
```json
{ "message": "인증 코드가 재발송되었습니다" }
```

### POST `/auth/refresh` — 토큰 갱신

**Request Body:**
```json
{ "refresh_token": "eyJ..." }
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### GET `/auth/me` — 현재 사용자 정보 🔒

**Response:** `200 OK` — `UserResponse` (회원가입 응답과 동일)

### PUT `/auth/password` — 비밀번호 변경 🔒

**Request Body:**
```json
{
  "current_password": "oldpass1",
  "new_password": "newpass1"
}
```
- `new_password`: 8~100자

**Response:** `200 OK`
```json
{ "message": "비밀번호가 변경되었습니다" }
```

### DELETE `/auth/account` — 회원 탈퇴 🔒

**Request Body:**
```json
{ "password": "password1" }
```

**Response:** `200 OK`
```json
{ "message": "회원 탈퇴가 완료되었습니다" }
```

### PATCH `/auth/profile` — 프로필 수정 🔒

**Request Body:** (부분 업데이트)
```json
{
  "nickname": "새닉네임",
  "profile_image": "https://example.com/img.jpg"
}
```
- `nickname`: 2~20자 (선택)
- `profile_image`: 500자 이내 URL (선택)

**Response:** `200 OK` — `UserResponse`


---

## 2. 거래 (Transactions)

### POST `/transactions/` — 거래 생성 🔒

**Request Body:**
```json
{
  "date": "2026-03-01",
  "area": "GENERAL",
  "type": "EXPENSE",
  "major_category": "식비",
  "minor_category": "점심",
  "description": "김밥천국",
  "amount": 8000,
  "discount": 0,
  "asset_id": "uuid (선택)",
  "memo": "메모 (선택)",
  "source": "MANUAL",
  "is_private": false,
  "car_detail": null,
  "ceremony_event": null
}
```

- `amount`: 0보다 큰 정수 (필수)
- `area`가 `CAR`이면 `car_detail` 필수
- `area`가 `EVENT`이면 `ceremony_event` 필수

**car_detail 예시:**
```json
{
  "car_type": "FUEL",
  "fuel_amount_liter": 40.5,
  "fuel_unit_price": 1650,
  "odometer": 52000,
  "station_name": "SK주유소"
}
```

**ceremony_event 예시:**
```json
{
  "direction": "SENT",
  "event_type": "WEDDING",
  "person_name": "김철수",
  "relationship": "대학 동기",
  "venue": "서울 강남구"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "user_id": "uuid",
  "family_group_id": null,
  "date": "2026-03-01",
  "area": "GENERAL",
  "type": "EXPENSE",
  "major_category": "식비",
  "minor_category": "점심",
  "description": "김밥천국",
  "amount": 8000,
  "discount": 0,
  "actual_amount": 8000,
  "asset_id": null,
  "memo": null,
  "source": "MANUAL",
  "is_private": false,
  "created_at": "2026-03-01T12:00:00",
  "updated_at": null
}
```

### GET `/transactions/` — 거래 목록 조회 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| start_date | date | N | 시작일 |
| end_date | date | N | 종료일 |
| area | string | N | 영역 필터 (GENERAL, CAR, SUBSCRIPTION, EVENT) |
| type | string | N | 유형 필터 (INCOME, EXPENSE) |
| major_category | string | N | 대분류 카테고리 |
| asset_id | uuid | N | 자산 ID |
| family_group | bool | N | 가족 그룹 거래 포함 (기본 false) |
| offset | int | N | 페이지 오프셋 (기본 0) |
| limit | int | N | 페이지 크기 (기본 50, 최대 200) |

**Response:** `200 OK`
```json
{
  "items": [ /* TransactionResponse[] */ ],
  "total": 150,
  "offset": 0,
  "limit": 50
}
```

### GET `/transactions/{transaction_id}` — 거래 상세 조회 🔒

**Response:** `200 OK`
```json
{
  "id": 1,
  "...": "TransactionResponse 필드들",
  "car_detail": { "car_type": "FUEL", "..." },
  "ceremony_event": null
}
```

### PUT `/transactions/{transaction_id}` — 거래 수정 🔒

**Request Body:** (부분 업데이트, 모든 필드 선택)
```json
{
  "amount": 9000,
  "description": "수정된 설명"
}
```

**Response:** `200 OK` — `TransactionResponse`

### DELETE `/transactions/{transaction_id}` — 거래 삭제 🔒

**Response:** `204 No Content`


---

## 3. 카테고리 (Categories)

### POST `/categories/` — 카테고리 생성 🔒

**Request Body:**
```json
{
  "area": "GENERAL",
  "type": "EXPENSE",
  "major_category": "식비",
  "minor_categories": ["점심", "저녁", "간식"],
  "icon": "🍚",
  "color": "#FF5733"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "owner_id": "uuid",
  "owner_type": "USER",
  "area": "GENERAL",
  "type": "EXPENSE",
  "major_category": "식비",
  "minor_categories": ["점심", "저녁", "간식"],
  "icon": "🍚",
  "color": "#FF5733",
  "is_active": true,
  "is_default": false,
  "sort_order": 0,
  "created_at": "2026-03-01T00:00:00",
  "updated_at": null
}
```

### GET `/categories/` — 카테고리 목록 조회 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| area | string | N | 영역 필터 |
| type | string | N | 유형 필터 (INCOME, EXPENSE) |

**Response:** `200 OK` — `CategoryResponse[]`

### PUT `/categories/sort-order` — 정렬 순서 변경 🔒

**Request Body:**
```json
[
  { "id": "uuid", "sort_order": 0 },
  { "id": "uuid", "sort_order": 1 }
]
```

**Response:** `200 OK`
```json
{ "message": "정렬 순서가 변경되었습니다" }
```

### PUT `/categories/{category_id}` — 카테고리 수정 🔒

**Request Body:** (부분 업데이트)
```json
{
  "major_category": "외식비",
  "minor_categories": ["점심", "저녁"],
  "is_active": false
}
```

**Response:** `200 OK` — `CategoryResponse`

### DELETE `/categories/{category_id}` — 카테고리 삭제 🔒

기본 카테고리는 삭제 불가.

**Response:** `204 No Content`

---

## 4. 자산 (Assets)

### POST `/assets/` — 자산 생성 🔒

**Request Body:**
```json
{
  "name": "국민은행 통장",
  "asset_type": "BANK_ACCOUNT",
  "ownership": "PERSONAL",
  "institution": "국민은행",
  "balance": 1500000,
  "memo": "월급 통장",
  "icon": "🏦",
  "color": "#4A90D9"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "family_group_id": null,
  "ownership": "PERSONAL",
  "name": "국민은행 통장",
  "asset_type": "BANK_ACCOUNT",
  "institution": "국민은행",
  "balance": 1500000,
  "memo": "월급 통장",
  "icon": "🏦",
  "color": "#4A90D9",
  "is_active": true,
  "sort_order": 0,
  "created_at": "2026-03-01T00:00:00",
  "updated_at": null
}
```

### GET `/assets/` — 자산 목록 조회 🔒

**Response:** `200 OK` — `AssetResponse[]` (sort_order 오름차순)

### PUT `/assets/default` — 기본 자산 설정 🔒

**Request Body:**
```json
{ "asset_id": "uuid" }
```

**Response:** `200 OK`
```json
{ "message": "기본 자산이 설정되었습니다" }
```

### PUT `/assets/sort-order` — 정렬 순서 변경 🔒

**Request Body:**
```json
[
  { "asset_id": "uuid", "sort_order": 0 },
  { "asset_id": "uuid", "sort_order": 1 }
]
```

**Response:** `200 OK`
```json
{ "message": "정렬 순서가 변경되었습니다" }
```

### PUT `/assets/{asset_id}` — 자산 수정 🔒

**Request Body:** (부분 업데이트)

**Response:** `200 OK` — `AssetResponse`

### DELETE `/assets/{asset_id}` — 자산 삭제 🔒

**Response:** `204 No Content`


---

## 5. 가족 그룹 (Family)

### POST `/family/` — 가족 그룹 생성 🔒

**Request Body:**
```json
{ "name": "우리 가족" }
```
- `name`: 1~50자

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "우리 가족",
  "owner_id": "uuid",
  "created_at": "2026-03-01T00:00:00"
}
```

### POST `/family/join` — 그룹 참여 🔒

**Request Body:**
```json
{ "invite_code": "AB12CD34" }
```
- `invite_code`: 8자리 영숫자

**Response:** `200 OK` — `FamilyGroupResponse`

### GET `/family/members` — 멤버 목록 조회 🔒

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "nickname": "홍길동",
    "email": "user@example.com",
    "role_in_group": "OWNER",
    "created_at": "2026-03-01T00:00:00"
  }
]
```

### DELETE `/family/members/{member_id}` — 멤버 강퇴 🔒 (OWNER만)

**Response:** `204 No Content`

### POST `/family/invite-code` — 초대 코드 재생성 🔒 (OWNER만)

**Response:** `200 OK`
```json
{
  "invite_code": "XY56ZW78",
  "invite_code_expires_at": "2026-03-08T00:00:00"
}
```

### GET `/family/invite-code` — 초대 코드 조회 🔒

**Response:** `200 OK` — `InviteCodeResponse`

### POST `/family/leave` — 그룹 탈퇴 🔒 (MEMBER만)

**Response:** `200 OK`
```json
{ "message": "그룹에서 탈퇴했습니다" }
```

### DELETE `/family/` — 그룹 해산 🔒 (OWNER만)

**Response:** `204 No Content`

---

## 6. 구독 (Subscriptions)

### POST `/subscriptions/` — 구독 생성 🔒

**Request Body:**
```json
{
  "service_name": "Netflix",
  "category": "OTT",
  "amount": 17000,
  "cycle": "MONTHLY",
  "billing_day": 15,
  "asset_id": "uuid (선택)",
  "start_date": "2026-01-15",
  "end_date": null,
  "status": "ACTIVE",
  "notify_before_days": 1,
  "memo": null
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "family_group_id": null,
  "service_name": "Netflix",
  "category": "OTT",
  "amount": 17000,
  "cycle": "MONTHLY",
  "billing_day": 15,
  "asset_id": null,
  "start_date": "2026-01-15",
  "end_date": null,
  "status": "ACTIVE",
  "notify_before_days": 1,
  "memo": null,
  "created_at": "2026-03-01T00:00:00",
  "updated_at": null
}
```

### GET `/subscriptions/` — 구독 목록 조회 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| status | string | N | 상태 필터 (ACTIVE, PAUSED, CANCELLED) |

**Response:** `200 OK` — `SubscriptionResponse[]`

### GET `/subscriptions/summary` — 구독 요약 🔒

**Response:** `200 OK`
```json
{
  "monthly_total": 45000,
  "yearly_total": 540000,
  "active_count": 3
}
```

### GET `/subscriptions/{subscription_id}` — 구독 상세 🔒

**Response:** `200 OK`
```json
{
  "...": "SubscriptionResponse 필드들",
  "next_billing_date": "2026-04-15"
}
```

### PUT `/subscriptions/{subscription_id}` — 구독 수정 🔒

**Request Body:** (부분 업데이트)

**Response:** `200 OK` — `SubscriptionResponse`

### DELETE `/subscriptions/{subscription_id}` — 구독 삭제 🔒

**Response:** `204 No Content`

### POST `/subscriptions/batch/process` — 결제 자동 생성 배치 🔑

> 배치 API 키 인증 필요 (`X-Batch-API-Key` 헤더)

**Request Body:**
```json
{ "target_date": "2026-03-15" }
```

**Response:** `200 OK`
```json
{
  "processed_count": 5,
  "skipped_count": 2,
  "target_date": "2026-03-15"
}
```

### POST `/subscriptions/batch/notify` — 결제 전 알림 배치 🔑

> 배치 API 키 인증 필요

**Response:** `200 OK`
```json
{
  "notified_count": 3,
  "skipped_count": 1
}
```


---

## 7. 예산 (Budgets)

### POST `/budgets/` — 예산 생성 🔒

**Request Body:**
```json
{
  "year": 2026,
  "month": 3,
  "category": "식비",
  "budget_amount": 500000,
  "family_group_id": null
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "family_group_id": null,
  "year": 2026,
  "month": 3,
  "category": "식비",
  "budget_amount": 500000,
  "created_at": "2026-03-01T00:00:00",
  "updated_at": null
}
```

### GET `/budgets/` — 예산 목록 조회 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| year | int | Y | 연도 (2000~2100) |
| month | int | Y | 월 (1~12) |

**Response:** `200 OK` — `BudgetResponse[]`

### GET `/budgets/performance` — 예산 대비 실적 🔒

**Query Parameters:** year (필수), month (필수)

**Response:** `200 OK`
```json
[
  {
    "category": "식비",
    "budget_amount": 500000,
    "actual_amount": 320000,
    "remaining": 180000,
    "usage_rate": 64.0
  }
]
```

### PUT `/budgets/{budget_id}` — 예산 수정 🔒

**Request Body:** (부분 업데이트)
```json
{ "budget_amount": 600000 }
```

**Response:** `200 OK` — `BudgetResponse`

### DELETE `/budgets/{budget_id}` — 예산 삭제 🔒

**Response:** `204 No Content`

---

## 8. 목표 (Goals)

### POST `/goals/` — 목표 생성 🔒

**Request Body:**
```json
{
  "type": "MONTHLY_SAVING",
  "title": "3월 저축 목표",
  "target_amount": 1000000,
  "start_date": "2026-03-01",
  "end_date": "2026-03-31",
  "family_group_id": null
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "family_group_id": null,
  "type": "MONTHLY_SAVING",
  "title": "3월 저축 목표",
  "target_amount": 1000000,
  "current_amount": 0,
  "start_date": "2026-03-01",
  "end_date": "2026-03-31",
  "status": "ACTIVE",
  "created_at": "2026-03-01T00:00:00",
  "updated_at": null
}
```

### GET `/goals/` — 목표 목록 조회 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| status | string | N | 상태 필터 (ACTIVE, COMPLETED, FAILED) |

**Response:** `200 OK` — `GoalResponse[]`

### GET `/goals/{goal_id}` — 목표 상세 조회 🔒

**Response:** `200 OK`
```json
{
  "...": "GoalResponse 필드들",
  "progress_rate": 45.5
}
```

### PUT `/goals/{goal_id}` — 목표 수정 🔒

**Request Body:** (부분 업데이트)

**Response:** `200 OK` — `GoalResponse`

### DELETE `/goals/{goal_id}` — 목표 삭제 🔒

**Response:** `204 No Content`

---

## 9. 통계 (Stats)

### GET `/stats/weekly` — 주간 통계 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| date | date | Y | 기준 날짜 (해당 주 통계) |

**Response:** `200 OK`
```json
{
  "start_date": "2026-03-09",
  "end_date": "2026-03-15",
  "total_expense": 250000,
  "daily_average": 35714,
  "no_spend_days": 1,
  "daily_expenses": [
    { "date": "2026-03-09", "amount": 45000 }
  ],
  "area_breakdown": [
    { "area": "GENERAL", "amount": 200000, "ratio": 80.0 }
  ]
}
```

### GET `/stats/monthly` — 월간 통계 🔒

**Query Parameters:** year (필수), month (필수)

**Response:** `200 OK`
```json
{
  "year": 2026,
  "month": 3,
  "total_income": 3500000,
  "total_expense": 2100000,
  "balance": 1400000,
  "category_breakdown": [
    { "category": "식비", "amount": 500000, "ratio": 23.8, "prev_month_change_rate": 5.2 }
  ],
  "budget_vs_actual": [
    { "category": "식비", "budget_amount": 500000, "actual_amount": 500000, "remaining": 0, "usage_rate": 100.0 }
  ],
  "prev_month_change_rate": -3.5,
  "asset_breakdown": [
    { "asset_id": "uuid", "amount": 1500000, "ratio": 71.4 }
  ]
}
```

### GET `/stats/yearly` — 연간 통계 🔒

**Query Parameters:** year (필수)

**Response:** `200 OK`
```json
{
  "year": 2026,
  "monthly_trends": [
    { "month": 1, "income": 3500000, "expense": 2100000 }
  ],
  "total_income": 42000000,
  "total_expense": 25200000,
  "savings": 16800000,
  "savings_rate": 40.0,
  "top_categories": [
    { "category": "식비", "amount": 6000000, "ratio": 23.8 }
  ],
  "ceremony_summary": { "sent_total": 500000, "received_total": 300000 },
  "subscription_summary": { "total_expense": 540000, "active_count": 3, "cancelled_count": 1 }
}
```


---

## 10. 정산 (Settlement)

### GET `/settlement/usage` — 가족 카드 사용 현황 🔒

**Query Parameters:** year (필수), month (필수)

**Response:** `200 OK`
```json
{
  "year": 2026,
  "month": 3,
  "family_total_expense": 3200000,
  "members": [
    {
      "user_id": "uuid",
      "nickname": "홍길동",
      "total_expense": 1800000,
      "asset_expenses": [
        { "asset_id": "uuid", "amount": 1200000 }
      ]
    }
  ]
}
```

### GET `/settlement/calculate` — 정산 계산 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| year | int | Y | 연도 |
| month | int | Y | 월 |
| ratio | string | N | 정산 비율 (예: "60:40") |

**Response:** `200 OK`
```json
{
  "year": 2026,
  "month": 3,
  "family_total_expense": 3200000,
  "split_method": "equal",
  "members": [
    {
      "user_id": "uuid",
      "nickname": "홍길동",
      "actual_expense": 1800000,
      "expense_ratio": 56.25,
      "share_amount": 1600000,
      "difference": 200000
    }
  ],
  "transfers": [
    {
      "from_user_id": "uuid",
      "from_nickname": "김영희",
      "to_user_id": "uuid",
      "to_nickname": "홍길동",
      "amount": 200000
    }
  ]
}
```

---

## 11. 이체 (Transfers)

### POST `/transfers/` — 이체 생성 🔒

**Request Body:**
```json
{
  "from_asset_id": "uuid",
  "to_asset_id": "uuid",
  "amount": 500000,
  "fee": 0,
  "description": "적금 이체",
  "transfer_date": "2026-03-01"
}
```
- `from_asset_id`와 `to_asset_id`는 서로 달라야 함

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "family_group_id": null,
  "from_asset_id": "uuid",
  "to_asset_id": "uuid",
  "amount": 500000,
  "fee": 0,
  "description": "적금 이체",
  "transfer_date": "2026-03-01",
  "created_at": "2026-03-01T00:00:00",
  "updated_at": null
}
```

### GET `/transfers/` — 이체 목록 조회 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| start_date | date | N | 시작일 |
| end_date | date | N | 종료일 |

**Response:** `200 OK`
```json
[
  {
    "...": "TransferResponse 필드들",
    "from_asset_name": "국민은행 통장",
    "to_asset_name": "적금 계좌"
  }
]
```

### GET `/transfers/{transfer_id}` — 이체 상세 조회 🔒

**Response:** `200 OK` — `TransferDetailResponse`

### PUT `/transfers/{transfer_id}` — 이체 수정 🔒

**Request Body:** (부분 업데이트)
```json
{
  "amount": 600000,
  "description": "수정된 설명"
}
```

**Response:** `200 OK` — `TransferResponse`

### DELETE `/transfers/{transfer_id}` — 이체 삭제 🔒

자산 잔액이 원복됩니다.

**Response:** `204 No Content`

---

## 12. 데이터 내보내기 (Export)

### GET `/export/csv` — CSV 내보내기 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| start_date | date | Y | 시작일 |
| end_date | date | Y | 종료일 |
| category | string | N | 대분류 카테고리 필터 |
| area | string | N | 영역 필터 |

**Response:** `200 OK` — CSV 파일 다운로드  
`Content-Type: text/csv; charset=utf-8`

### GET `/export/xlsx` — 엑셀 내보내기 🔒

**Query Parameters:** CSV와 동일

**Response:** `200 OK` — XLSX 파일 다운로드  
`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`


---

## 13. AI 채팅 (AI Chat)

### POST `/ai/chat/sessions` — 세션 생성 🔒

**Request Body:**
```json
{ "title": "3월 가계부 정리" }
```
- `title`: 200자 이내 (선택)

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "3월 가계부 정리",
  "created_at": "2026-03-01T00:00:00",
  "updated_at": null
}
```

### GET `/ai/chat/sessions` — 세션 목록 조회 🔒

**Response:** `200 OK` — `ChatSessionResponse[]`

### GET `/ai/chat/sessions/{session_id}` — 세션 상세 (메시지 포함) 🔒

**Response:** `200 OK`
```json
{
  "session": { "id": "uuid", "..." },
  "messages": [
    {
      "id": "uuid",
      "session_id": "uuid",
      "role": "USER",
      "content": "오늘 점심 김밥천국에서 8000원 썼어",
      "extracted_data": null,
      "created_at": "2026-03-01T12:00:00"
    },
    {
      "id": "uuid",
      "session_id": "uuid",
      "role": "ASSISTANT",
      "content": "거래를 등록했습니다.",
      "extracted_data": {
        "date": "2026-03-01",
        "area": "GENERAL",
        "type": "EXPENSE",
        "major_category": "식비",
        "description": "김밥천국",
        "amount": 8000
      },
      "created_at": "2026-03-01T12:00:01"
    }
  ]
}
```

### DELETE `/ai/chat/sessions/{session_id}` — 세션 삭제 🔒

**Response:** `204 No Content`

### POST `/ai/chat/sessions/{session_id}/messages` — 메시지 전송 🔒

**Request Body:**
```json
{ "content": "오늘 점심 김밥천국에서 8000원 썼어" }
```
- `content`: 1~2000자

**Response:** `201 Created` — `ChatMessageResponse`

AI 서비스 오류 시 `502` 응답.

### POST `/ai/chat/messages/{message_id}/confirm` — 거래 확정 🔒

AI가 추출한 거래 데이터를 확정하여 실제 거래를 생성합니다.

**Request Body:** (선택, 수정할 필드만)
```json
{
  "overrides": {
    "amount": 9000,
    "major_category": "외식비"
  }
}
```

**Response:** `201 Created` — `TransactionResponse`

---

## 14. 영수증 OCR (Receipts)

### POST `/ai/receipts/scan` — 영수증 스캔 🔒

**Request:** `multipart/form-data`

| 필드 | 타입 | 설명 |
|------|------|------|
| file | File | JPEG 또는 PNG 이미지 (최대 10MB) |

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "image_url": null,
  "raw_text": "OCR 추출 텍스트",
  "extracted_data": {
    "date": "2026-03-01",
    "description": "스타벅스",
    "amount": 5500
  },
  "status": "COMPLETED",
  "transaction_id": null,
  "created_at": "2026-03-01T00:00:00",
  "updated_at": null
}
```

### GET `/ai/receipts/` — 스캔 이력 조회 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| status | string | N | 상태 필터 (PENDING, COMPLETED, FAILED) |

**Response:** `200 OK` — `ReceiptScanResponse[]`

### GET `/ai/receipts/{scan_id}` — 스캔 상세 조회 🔒

**Response:** `200 OK` — `ReceiptScanResponse`

### POST `/ai/receipts/{scan_id}/confirm` — OCR 거래 확정 🔒

**Request Body:** (선택)
```json
{
  "overrides": {
    "amount": 6000,
    "major_category": "카페"
  }
}
```

**Response:** `201 Created` — `TransactionResponse`

---

## 15. AI 분석 (AI Analysis)

### GET `/ai/analysis/monthly` — 월간 지출 분석 🔒

**Query Parameters:** year (필수), month (필수)

**Response:** `200 OK`
```json
{
  "year": 2026,
  "month": 3,
  "summary": "이번 달 총 지출은 210만원으로...",
  "category_trends": [
    {
      "category": "식비",
      "current_amount": 500000,
      "previous_amount": 480000,
      "change_rate": 4.2,
      "direction": "increase"
    }
  ]
}
```

### GET `/ai/analysis/savings-tips` — 절약 제안 🔒

**Query Parameters:** year (필수), month (필수)

**Response:** `200 OK`
```json
{
  "year": 2026,
  "month": 3,
  "over_budget_categories": [
    {
      "category": "외식비",
      "budget_amount": 300000,
      "actual_amount": 420000,
      "over_amount": 120000
    }
  ],
  "tips": "외식비가 예산을 40% 초과했습니다. 주 2회 도시락을 준비하면...",
  "message": null
}
```

---

## 16. AI 피드백 (AI Feedbacks)

### POST `/ai/feedbacks/` — 피드백 제출 🔒

**Request Body:**
```json
{
  "transaction_id": 1,
  "feedback_type": "CATEGORY_CORRECTION",
  "original_value": "식비",
  "corrected_value": "카페"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "transaction_id": 1,
  "feedback_type": "CATEGORY_CORRECTION",
  "original_value": "식비",
  "corrected_value": "카페",
  "created_at": "2026-03-01T00:00:00"
}
```

### GET `/ai/feedbacks/` — 피드백 이력 조회 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| feedback_type | string | N | 피드백 유형 필터 |
| transaction_id | int | N | 거래 ID 필터 |

**Response:** `200 OK`
```json
[
  {
    "...": "FeedbackResponse 필드들",
    "transaction_description": "김밥천국",
    "transaction_date": "2026-03-01"
  }
]
```

---

## 17. 알림 (Notifications)

### GET `/notifications/` — 알림 목록 조회 🔒

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "subscription_id": "uuid",
    "type": "PAYMENT_REMINDER",
    "title": "Netflix 결제 예정",
    "message": "내일 Netflix 17,000원이 결제됩니다.",
    "is_read": false,
    "created_at": "2026-03-14T00:00:00"
  }
]
```

### PATCH `/notifications/{notification_id}/read` — 읽음 처리 🔒

**Response:** `200 OK` — `NotificationResponse` (is_read: true)

---

## 18. 경조사 인물 (Ceremony Persons)

### GET `/ceremony-persons/` — 인물 목록 검색 🔒

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| query | string | N | 이름 또는 관계 검색어 |

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "name": "김철수",
    "relationship": "대학 동기",
    "total_sent": 300000,
    "total_received": 100000,
    "event_count": 3,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": null
  }
]
```

### GET `/ceremony-persons/{person_id}/transactions` — 인물 거래 이력 🔒

**Response:** `200 OK` — `TransactionResponse[]` (날짜 내림차순)


---

## 19. 헬스체크 (Health)

> 이 엔드포인트는 `/api/v1` 프리픽스 없이 루트에 등록됩니다.

### GET `/health` — 상태 확인

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "0.1.0"
}
```

---

## 20. Enum 타입 정의

### Area (거래 영역)
| 값 | 설명 |
|----|------|
| GENERAL | 일반 |
| CAR | 차계부 |
| SUBSCRIPTION | 구독 |
| EVENT | 경조사 |

### TransactionType (거래 유형)
| 값 | 설명 |
|----|------|
| INCOME | 수입 |
| EXPENSE | 지출 |

### TransactionSource (거래 입력 출처)
| 값 | 설명 |
|----|------|
| MANUAL | 수동 입력 |
| AI_CHAT | AI 채팅 |
| RECEIPT_SCAN | 영수증 스캔 |
| SUBSCRIPTION_AUTO | 구독 자동 생성 |

### CarType (차계부 비용 유형)
| 값 | 설명 |
|----|------|
| FUEL | 주유 |
| MAINTENANCE | 정비 |
| INSURANCE | 보험 |
| TAX | 세금 |
| TOLL | 통행료 |
| PARKING | 주차 |
| WASH | 세차 |
| INSTALLMENT | 할부금 |
| OTHER | 기타 |

### CeremonyDirection (경조사 방향)
| 값 | 설명 |
|----|------|
| SENT | 보낸 |
| RECEIVED | 받은 |

### CeremonyEventType (경조사 이벤트 유형)
| 값 | 설명 |
|----|------|
| WEDDING | 결혼 |
| FUNERAL | 장례 |
| FIRST_BIRTHDAY | 돌잔치 |
| BIRTHDAY | 생일 |
| HOUSEWARMING | 집들이 |
| OPENING | 개업 |
| HOLIDAY | 명절 |
| OTHER | 기타 |

### AssetType (자산 유형)
| 값 | 설명 |
|----|------|
| BANK_ACCOUNT | 은행 계좌 |
| CREDIT_CARD | 신용카드 |
| DEBIT_CARD | 체크카드 |
| CASH | 현금 |
| INVESTMENT | 투자 |
| OTHER | 기타 |

### Ownership (소유권)
| 값 | 설명 |
|----|------|
| PERSONAL | 개인 |
| SHARED | 공유 |

### GroupRole (가족 그룹 역할)
| 값 | 설명 |
|----|------|
| OWNER | 그룹장 |
| MEMBER | 멤버 |

### SubscriptionCategory (구독 카테고리)
| 값 | 설명 |
|----|------|
| OTT | OTT |
| MUSIC | 음악 |
| CLOUD | 클라우드 |
| PRODUCTIVITY | 생산성 |
| AI | AI |
| GAME | 게임 |
| NEWS | 뉴스 |
| OTHER | 기타 |

### SubscriptionCycle (구독 결제 주기)
| 값 | 설명 |
|----|------|
| MONTHLY | 월간 |
| YEARLY | 연간 |
| WEEKLY | 주간 |

### SubscriptionStatus (구독 상태)
| 값 | 설명 |
|----|------|
| ACTIVE | 활성 |
| PAUSED | 일시정지 |
| CANCELLED | 해지 |

### GoalType (목표 유형)
| 값 | 설명 |
|----|------|
| MONTHLY_SAVING | 월 저축 |
| SAVING_RATE | 저축률 |
| SPECIAL | 특별 목표 |

### GoalStatus (목표 상태)
| 값 | 설명 |
|----|------|
| ACTIVE | 진행 중 |
| COMPLETED | 달성 |
| FAILED | 실패 |

### MessageRole (AI 채팅 역할)
| 값 | 설명 |
|----|------|
| USER | 사용자 |
| ASSISTANT | AI |

### ScanStatus (영수증 스캔 상태)
| 값 | 설명 |
|----|------|
| PENDING | 처리 중 |
| COMPLETED | 완료 |
| FAILED | 실패 |

### FeedbackType (AI 피드백 유형)
| 값 | 설명 |
|----|------|
| CATEGORY_CORRECTION | 카테고리 수정 |
| AMOUNT_CORRECTION | 금액 수정 |
| DESCRIPTION_CORRECTION | 설명 수정 |
