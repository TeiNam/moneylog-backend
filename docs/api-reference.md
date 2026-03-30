# MoneyLog API 레퍼런스

Base URL: `/api/v1`

인증: `Authorization: Bearer <access_token>` (헬스체크, 회원가입, 로그인, OAuth 제외)

## 목차

- [헬스체크](#health) — 1개 엔드포인트
- [인증](#auth) — 11개 엔드포인트
- [자산 관리](#assets) — 6개 엔드포인트
- [카드 결제 주기 / 청구할인](#billing) — 8개 엔드포인트
- [거래](#transactions) — 5개 엔드포인트
- [이체](#transfers) — 5개 엔드포인트
- [카테고리](#categories) — 5개 엔드포인트
- [예산](#budgets) — 5개 엔드포인트
- [목표](#goals) — 5개 엔드포인트
- [구독](#subscriptions) — 8개 엔드포인트
- [알림](#notifications) — 2개 엔드포인트
- [경조사 인물](#ceremony-persons) — 2개 엔드포인트
- [가족 카드 정산](#settlement) — 2개 엔드포인트
- [통계](#stats) — 3개 엔드포인트
- [내보내기](#export) — 2개 엔드포인트
- [파일 업로드](#upload) — 1개 엔드포인트
- [AI 채팅](#ai-chat) — 6개 엔드포인트
- [영수증 OCR](#receipts) — 4개 엔드포인트
- [AI 분석](#ai-analysis) — 2개 엔드포인트
- [AI 피드백](#ai-feedbacks) — 2개 엔드포인트

---

## 헬스체크
<a id="health"></a>

### `GET /health`

Health Check

**응답 `200`:** `HealthResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `status` | `string` | ✅ | Status |
| `database` | `string` | ✅ | Database |
| `version` | `string` | ✅ | Version |

---

## 인증
<a id="auth"></a>

### `DELETE /api/v1/auth/account`

회원 탈퇴

**요청 바디:** `DeactivateAccountRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `password` | `string` | ✅ | Password |

---

### `POST /api/v1/auth/login`

로그인

**요청 바디:** `LoginRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `email` | `string(email)` | ✅ | Email |
| `password` | `string` | ✅ | Password |

**응답 `200`:** `TokenResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `access_token` | `string` | ✅ | Access Token |
| `refresh_token` | `string` | ✅ | Refresh Token |
| `token_type` | `string` |  | Token Type |

---

### `GET /api/v1/auth/me`

현재 사용자 정보

**응답 `200`:** `UserResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `email` | `` | ✅ | Email |
| `nickname` | `` | ✅ | Nickname |
| `auth_provider` | `` | ✅ | Auth Provider |
| `email_verified` | `` | ✅ | Email Verified |
| `status` | `` | ✅ | Status |
| `created_at` | `` | ✅ | Created At |

---

### `GET /api/v1/auth/oauth/{provider}/authorize`

OAuth 인가 URL 반환

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `provider` | path | `OAuthProvider` | ✅ |  |

**응답 `200`:** `OAuthAuthorizationResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `authorization_url` | `string` | ✅ | Authorization Url |
| `state` | `string` | ✅ | State |

---

### `POST /api/v1/auth/oauth/{provider}/callback`

OAuth 콜백 처리

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `provider` | path | `OAuthProvider` | ✅ |  |

**요청 바디:** `OAuthCallbackRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `code` | `string` | ✅ | Code |
| `state` | `string` | ✅ | State |

**응답 `200`:** `TokenResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `access_token` | `string` | ✅ | Access Token |
| `refresh_token` | `string` | ✅ | Refresh Token |
| `token_type` | `string` |  | Token Type |

---

### `PUT /api/v1/auth/password`

비밀번호 변경

**요청 바디:** `ChangePasswordRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `current_password` | `string` | ✅ | Current Password |
| `new_password` | `string` | ✅ | New Password (minLen=8, maxLen=100) |

---

### `PATCH /api/v1/auth/profile`

프로필 수정

**요청 바디:** `UpdateProfileRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `nickname` | `string | null` |  | Nickname |
| `profile_image` | `string | null` |  | Profile Image |

**응답 `200`:** `UserResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `email` | `` | ✅ | Email |
| `nickname` | `` | ✅ | Nickname |
| `auth_provider` | `` | ✅ | Auth Provider |
| `email_verified` | `` | ✅ | Email Verified |
| `status` | `` | ✅ | Status |
| `created_at` | `` | ✅ | Created At |

---

### `POST /api/v1/auth/refresh`

토큰 갱신

**요청 바디:** `RefreshTokenRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `refresh_token` | `string` | ✅ | Refresh Token |

**응답 `200`:** `AccessTokenResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `access_token` | `string` | ✅ | Access Token |
| `token_type` | `string` |  | Token Type |

---

### `POST /api/v1/auth/register`

회원가입

**요청 바디:** `RegisterRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `email` | `string(email)` | ✅ | Email |
| `password` | `string` | ✅ | Password (minLen=8) |
| `nickname` | `string` | ✅ | Nickname (minLen=1, maxLen=100) |

**응답 `201`:** `UserResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `email` | `` | ✅ | Email |
| `nickname` | `` | ✅ | Nickname |
| `auth_provider` | `` | ✅ | Auth Provider |
| `email_verified` | `` | ✅ | Email Verified |
| `status` | `` | ✅ | Status |
| `created_at` | `` | ✅ | Created At |

---

### `POST /api/v1/auth/resend-verification`

인증 코드 재발송

**요청 바디:** `ResendVerificationRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `email` | `string(email)` | ✅ | Email |

---

### `POST /api/v1/auth/verify-email`

이메일 인증

**요청 바디:** `VerifyEmailRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `email` | `string(email)` | ✅ | Email |
| `code` | `string` | ✅ | Code (minLen=6, maxLen=6) |

---

## 자산 관리
<a id="assets"></a>

### `GET /api/v1/assets/`

자산 목록 조회

**응답 `200`:** `list[AssetResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `ownership` | `` | ✅ | Ownership |
| `name` | `` | ✅ | Name |
| `asset_type` | `` | ✅ | Asset Type |
| `institution` | `` | ✅ | Institution |
| `balance` | `` | ✅ | Balance |
| `memo` | `` | ✅ | Memo |
| `icon` | `` | ✅ | Icon |
| `color` | `` | ✅ | Color |
| `is_active` | `` | ✅ | Is Active |
| `sort_order` | `` | ✅ | Sort Order |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `POST /api/v1/assets/`

자산 생성

**요청 바디:** `AssetCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `name` | `string` | ✅ | Name (minLen=1) |
| `asset_type` | `AssetType` | ✅ | 자산 유형 |
| `ownership` | `Ownership` |  | 소유권 구분 |
| `family_group_id` | `string(uuid) | null` |  | Family Group Id |
| `institution` | `string | null` |  | Institution |
| `balance` | `integer | null` |  | Balance |
| `memo` | `string | null` |  | Memo |
| `icon` | `string | null` |  | Icon |
| `color` | `string | null` |  | Color |

**응답 `201`:** `AssetResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `ownership` | `` | ✅ | Ownership |
| `name` | `` | ✅ | Name |
| `asset_type` | `` | ✅ | Asset Type |
| `institution` | `` | ✅ | Institution |
| `balance` | `` | ✅ | Balance |
| `memo` | `` | ✅ | Memo |
| `icon` | `` | ✅ | Icon |
| `color` | `` | ✅ | Color |
| `is_active` | `` | ✅ | Is Active |
| `sort_order` | `` | ✅ | Sort Order |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `PUT /api/v1/assets/default`

기본 자산 설정

**요청 바디:** `DefaultAssetRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `asset_id` | `string(uuid)` | ✅ | Asset Id |

---

### `PUT /api/v1/assets/sort-order`

자산 정렬 순서 일괄 변경

---

### `PUT /api/v1/assets/{asset_id}`

자산 수정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `asset_id` | path | `string(uuid)` | ✅ | Asset Id |

**요청 바디:** `AssetUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `name` | `string | null` |  | Name |
| `asset_type` | `AssetType | null` |  | 자산 유형 |
| `institution` | `string | null` |  | Institution |
| `balance` | `integer | null` |  | Balance |
| `memo` | `string | null` |  | Memo |
| `icon` | `string | null` |  | Icon |
| `color` | `string | null` |  | Color |
| `is_active` | `boolean | null` |  | Is Active |

**응답 `200`:** `AssetResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `ownership` | `` | ✅ | Ownership |
| `name` | `` | ✅ | Name |
| `asset_type` | `` | ✅ | Asset Type |
| `institution` | `` | ✅ | Institution |
| `balance` | `` | ✅ | Balance |
| `memo` | `` | ✅ | Memo |
| `icon` | `` | ✅ | Icon |
| `color` | `` | ✅ | Color |
| `is_active` | `` | ✅ | Is Active |
| `sort_order` | `` | ✅ | Sort Order |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `DELETE /api/v1/assets/{asset_id}`

자산 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `asset_id` | path | `string(uuid)` | ✅ | Asset Id |

**응답 `204`:** No Content

---

## 카드 결제 주기 / 청구할인
<a id="billing"></a>

### `GET /api/v1/assets/{asset_id}/billing/config`

결제 주기 설정 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `asset_id` | path | `string(uuid)` | ✅ | Asset Id |

**응답 `200`:** `BillingConfigResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `asset_id` | `string(uuid)` | ✅ | Asset Id |
| `payment_day` | `integer | null` | ✅ | Payment Day |
| `billing_start_day` | `integer | null` | ✅ | Billing Start Day |
| `current_cycle` | `BillingCycleResponse | null` | ✅ |  |

---

### `PUT /api/v1/assets/{asset_id}/billing/config`

결제 주기 설정 변경

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `asset_id` | path | `string(uuid)` | ✅ | Asset Id |

**요청 바디:** `BillingConfigUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `payment_day` | `integer` | ✅ | Payment Day (min=1.0, max=31.0) |
| `billing_start_day` | `integer | null` |  | Billing Start Day |

**응답 `200`:** `BillingConfigResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `asset_id` | `string(uuid)` | ✅ | Asset Id |
| `payment_day` | `integer | null` | ✅ | Payment Day |
| `billing_start_day` | `integer | null` | ✅ | Billing Start Day |
| `current_cycle` | `BillingCycleResponse | null` | ✅ |  |

---

### `GET /api/v1/assets/{asset_id}/billing/cycle`

결제 주기 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `asset_id` | path | `string(uuid)` | ✅ | Asset Id |
| `reference_date` | query | `string(date) | null` |  | Reference Date |

**응답 `200`:** `BillingCycleResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `start_date` | `string(date)` | ✅ | Start Date |
| `end_date` | `string(date)` | ✅ | End Date |
| `payment_date` | `string(date)` | ✅ | Payment Date |

---

### `POST /api/v1/assets/{asset_id}/billing/discounts`

청구할인 등록

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `asset_id` | path | `string(uuid)` | ✅ | Asset Id |

**요청 바디:** `BillingDiscountCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `name` | `string` | ✅ | Name (minLen=1, maxLen=100) |
| `amount` | `integer` | ✅ | Amount (min=0.0) |
| `cycle_start` | `string(date)` | ✅ | Cycle Start |
| `cycle_end` | `string(date)` | ✅ | Cycle End |
| `memo` | `string | null` |  | Memo |

**응답 `201`:** `BillingDiscountResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `asset_id` | `` | ✅ | Asset Id |
| `name` | `` | ✅ | Name |
| `amount` | `` | ✅ | Amount |
| `cycle_start` | `` | ✅ | Cycle Start |
| `cycle_end` | `` | ✅ | Cycle End |
| `memo` | `` | ✅ | Memo |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/assets/{asset_id}/billing/summary`

결제 예정 금액 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `asset_id` | path | `string(uuid)` | ✅ | Asset Id |
| `reference_date` | query | `string(date) | null` |  | Reference Date |

**응답 `200`:** `BillingSummaryResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `cycle` | `BillingCycleResponse` | ✅ |  |
| `total_usage` | `integer` | ✅ | Total Usage |
| `total_discount` | `integer` | ✅ | Total Discount |
| `estimated_payment` | `integer` | ✅ | Estimated Payment |
| `next_payment_date` | `string(date)` | ✅ | Next Payment Date |

---

### `GET /api/v1/assets/{asset_id}/billing/transactions`

결제 주기별 거래 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `asset_id` | path | `string(uuid)` | ✅ | Asset Id |
| `reference_date` | query | `string(date) | null` |  | Reference Date |

**응답 `200`:** `BillingTransactionsResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `cycle` | `BillingCycleResponse` | ✅ |  |
| `transactions` | `list[TransactionResponse]` | ✅ | Transactions |
| `total_count` | `integer` | ✅ | Total Count |

---

### `PUT /api/v1/billing/discounts/{discount_id}`

청구할인 수정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `discount_id` | path | `string(uuid)` | ✅ | Discount Id |

**요청 바디:** `BillingDiscountUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `name` | `string | null` |  | Name |
| `amount` | `integer | null` |  | Amount |
| `memo` | `string | null` |  | Memo |

**응답 `200`:** `BillingDiscountResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `asset_id` | `` | ✅ | Asset Id |
| `name` | `` | ✅ | Name |
| `amount` | `` | ✅ | Amount |
| `cycle_start` | `` | ✅ | Cycle Start |
| `cycle_end` | `` | ✅ | Cycle End |
| `memo` | `` | ✅ | Memo |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `DELETE /api/v1/billing/discounts/{discount_id}`

청구할인 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `discount_id` | path | `string(uuid)` | ✅ | Discount Id |

**응답 `204`:** No Content

---

## 거래
<a id="transactions"></a>

### `POST /api/v1/transactions/`

거래 생성

**요청 바디:** `TransactionCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `date` | `string(date)` | ✅ | Date |
| `area` | `Area` | ✅ | 거래 영역 |
| `type` | `TransactionType` | ✅ | 거래 유형 |
| `major_category` | `string` | ✅ | Major Category |
| `minor_category` | `string` |  | Minor Category |
| `description` | `string` |  | Description |
| `amount` | `integer` | ✅ | Amount (>0.0) |
| `discount` | `integer` |  | Discount |
| `asset_id` | `string(uuid) | null` |  | Asset Id |
| `memo` | `string | null` |  | Memo |
| `source` | `TransactionSource` |  |  |
| `car_detail` | `CarExpenseDetailSchema | null` |  |  |
| `ceremony_event` | `CeremonyEventSchema | null` |  |  |
| `is_private` | `boolean` |  | Is Private |

**응답 `201`:** `TransactionResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `date` | `` | ✅ | Date |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_category` | `` | ✅ | Minor Category |
| `description` | `` | ✅ | Description |
| `amount` | `` | ✅ | Amount |
| `discount` | `` | ✅ | Discount |
| `actual_amount` | `` | ✅ | Actual Amount |
| `asset_id` | `` | ✅ | Asset Id |
| `memo` | `` | ✅ | Memo |
| `source` | `` | ✅ | Source |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `is_private` | `` | ✅ | Is Private |

---

### `GET /api/v1/transactions/`

거래 목록 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `start_date` | query | `string | null` |  | 시작일 (YYYY-MM-DD 또는 ISO 8601) |
| `end_date` | query | `string | null` |  | 종료일 (YYYY-MM-DD 또는 ISO 8601) |
| `area` | query | `Area | null` |  | Area |
| `type` | query | `TransactionType | null` |  | Type |
| `major_category` | query | `string | null` |  | Major Category |
| `asset_id` | query | `string(uuid) | null` |  | Asset Id |
| `family_group` | query | `boolean` |  | Family Group |
| `offset` | query | `integer` |  | Offset |
| `limit` | query | `integer` |  | Limit |

---

### `GET /api/v1/transactions/{transaction_id}`

거래 단건 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `transaction_id` | path | `integer` | ✅ | Transaction Id |

**응답 `200`:** `TransactionDetailResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `date` | `` | ✅ | Date |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_category` | `` | ✅ | Minor Category |
| `description` | `` | ✅ | Description |
| `amount` | `` | ✅ | Amount |
| `discount` | `` | ✅ | Discount |
| `actual_amount` | `` | ✅ | Actual Amount |
| `asset_id` | `` | ✅ | Asset Id |
| `memo` | `` | ✅ | Memo |
| `source` | `` | ✅ | Source |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `is_private` | `` | ✅ | Is Private |
| `car_detail` | `` |  |  |
| `ceremony_event` | `` |  |  |

---

### `PUT /api/v1/transactions/{transaction_id}`

거래 수정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `transaction_id` | path | `integer` | ✅ | Transaction Id |

**요청 바디:** `TransactionUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `date` | `string(date) | null` |  | Date |
| `area` | `Area | null` |  | 거래 영역 |
| `type` | `TransactionType | null` |  | 거래 유형 |
| `major_category` | `string | null` |  | Major Category |
| `minor_category` | `string | null` |  | Minor Category |
| `description` | `string | null` |  | Description |
| `amount` | `integer | null` |  | Amount |
| `discount` | `integer | null` |  | Discount |
| `asset_id` | `string(uuid) | null` |  | Asset Id |
| `memo` | `string | null` |  | Memo |
| `car_detail` | `CarExpenseDetailSchema | null` |  |  |
| `ceremony_event` | `CeremonyEventSchema | null` |  |  |
| `is_private` | `boolean | null` |  | Is Private |

**응답 `200`:** `TransactionResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `date` | `` | ✅ | Date |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_category` | `` | ✅ | Minor Category |
| `description` | `` | ✅ | Description |
| `amount` | `` | ✅ | Amount |
| `discount` | `` | ✅ | Discount |
| `actual_amount` | `` | ✅ | Actual Amount |
| `asset_id` | `` | ✅ | Asset Id |
| `memo` | `` | ✅ | Memo |
| `source` | `` | ✅ | Source |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `is_private` | `` | ✅ | Is Private |

---

### `DELETE /api/v1/transactions/{transaction_id}`

거래 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `transaction_id` | path | `integer` | ✅ | Transaction Id |

**응답 `204`:** No Content

---

## 이체
<a id="transfers"></a>

### `POST /api/v1/transfers/`

이체 생성

**요청 바디:** `TransferCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `from_asset_id` | `string(uuid)` | ✅ | From Asset Id |
| `to_asset_id` | `string(uuid)` | ✅ | To Asset Id |
| `amount` | `integer` | ✅ | Amount (>0.0) |
| `fee` | `integer` |  | Fee (min=0.0) |
| `description` | `string | null` |  | Description |
| `transfer_date` | `string(date)` | ✅ | Transfer Date |

**응답 `201`:** `TransferResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `from_asset_id` | `` | ✅ | From Asset Id |
| `to_asset_id` | `` | ✅ | To Asset Id |
| `amount` | `` | ✅ | Amount |
| `fee` | `` | ✅ | Fee |
| `description` | `` | ✅ | Description |
| `transfer_date` | `` | ✅ | Transfer Date |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/transfers/`

이체 내역 목록 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `start_date` | query | `string(date) | null` |  | 시작일 필터 |
| `end_date` | query | `string(date) | null` |  | 종료일 필터 |

**응답 `200`:** `list[TransferDetailResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `from_asset_id` | `` | ✅ | From Asset Id |
| `to_asset_id` | `` | ✅ | To Asset Id |
| `amount` | `` | ✅ | Amount |
| `fee` | `` | ✅ | Fee |
| `description` | `` | ✅ | Description |
| `transfer_date` | `` | ✅ | Transfer Date |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `from_asset_name` | `` | ✅ | From Asset Name |
| `to_asset_name` | `` | ✅ | To Asset Name |

---

### `GET /api/v1/transfers/{transfer_id}`

이체 상세 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `transfer_id` | path | `string(uuid)` | ✅ | Transfer Id |

**응답 `200`:** `TransferDetailResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `from_asset_id` | `` | ✅ | From Asset Id |
| `to_asset_id` | `` | ✅ | To Asset Id |
| `amount` | `` | ✅ | Amount |
| `fee` | `` | ✅ | Fee |
| `description` | `` | ✅ | Description |
| `transfer_date` | `` | ✅ | Transfer Date |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `from_asset_name` | `` | ✅ | From Asset Name |
| `to_asset_name` | `` | ✅ | To Asset Name |

---

### `PUT /api/v1/transfers/{transfer_id}`

이체 수정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `transfer_id` | path | `string(uuid)` | ✅ | Transfer Id |

**요청 바디:** `TransferUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `amount` | `integer | null` |  | Amount |
| `fee` | `integer | null` |  | Fee |
| `description` | `string | null` |  | Description |
| `transfer_date` | `string(date) | null` |  | Transfer Date |

**응답 `200`:** `TransferResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `from_asset_id` | `` | ✅ | From Asset Id |
| `to_asset_id` | `` | ✅ | To Asset Id |
| `amount` | `` | ✅ | Amount |
| `fee` | `` | ✅ | Fee |
| `description` | `` | ✅ | Description |
| `transfer_date` | `` | ✅ | Transfer Date |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `DELETE /api/v1/transfers/{transfer_id}`

이체 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `transfer_id` | path | `string(uuid)` | ✅ | Transfer Id |

**응답 `204`:** No Content

---

## 카테고리
<a id="categories"></a>

### `POST /api/v1/categories/`

카테고리 생성

**요청 바디:** `CategoryCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `area` | `Area` | ✅ |  |
| `type` | `TransactionType` | ✅ |  |
| `major_category` | `string` | ✅ | Major Category (minLen=1) |
| `minor_categories` | `list[string]` |  | Minor Categories |
| `icon` | `string | null` |  | Icon |
| `color` | `string | null` |  | Color |

**응답 `201`:** `CategoryResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `owner_id` | `` | ✅ | Owner Id |
| `owner_type` | `` | ✅ | Owner Type |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_categories` | `` | ✅ | Minor Categories |
| `icon` | `` | ✅ | Icon |
| `color` | `` | ✅ | Color |
| `is_active` | `` | ✅ | Is Active |
| `is_default` | `` | ✅ | Is Default |
| `sort_order` | `` | ✅ | Sort Order |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/categories/`

카테고리 목록 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `area` | query | `Area | null` |  | Area |
| `type` | query | `TransactionType | null` |  | Type |

**응답 `200`:** `list[CategoryResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `owner_id` | `` | ✅ | Owner Id |
| `owner_type` | `` | ✅ | Owner Type |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_categories` | `` | ✅ | Minor Categories |
| `icon` | `` | ✅ | Icon |
| `color` | `` | ✅ | Color |
| `is_active` | `` | ✅ | Is Active |
| `is_default` | `` | ✅ | Is Default |
| `sort_order` | `` | ✅ | Sort Order |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `PUT /api/v1/categories/sort-order`

카테고리 정렬 순서 일괄 변경

---

### `PUT /api/v1/categories/{category_id}`

카테고리 수정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `category_id` | path | `string(uuid)` | ✅ | Category Id |

**요청 바디:** `CategoryUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `major_category` | `string | null` |  | Major Category |
| `minor_categories` | `array | null` |  | Minor Categories |
| `icon` | `string | null` |  | Icon |
| `color` | `string | null` |  | Color |
| `is_active` | `boolean | null` |  | Is Active |

**응답 `200`:** `CategoryResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `owner_id` | `` | ✅ | Owner Id |
| `owner_type` | `` | ✅ | Owner Type |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_categories` | `` | ✅ | Minor Categories |
| `icon` | `` | ✅ | Icon |
| `color` | `` | ✅ | Color |
| `is_active` | `` | ✅ | Is Active |
| `is_default` | `` | ✅ | Is Default |
| `sort_order` | `` | ✅ | Sort Order |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `DELETE /api/v1/categories/{category_id}`

카테고리 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `category_id` | path | `string(uuid)` | ✅ | Category Id |

**응답 `204`:** No Content

---

## 예산
<a id="budgets"></a>

### `POST /api/v1/budgets/`

예산 생성

**요청 바디:** `BudgetCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `year` | `integer` | ✅ | Year (min=2000.0, max=2100.0) |
| `month` | `integer` | ✅ | Month (min=1.0, max=12.0) |
| `category` | `string` | ✅ | Category (minLen=1, maxLen=50) |
| `budget_amount` | `integer` | ✅ | Budget Amount (>0.0) |
| `family_group_id` | `string(uuid) | null` |  | Family Group Id |

**응답 `201`:** `BudgetResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `year` | `` | ✅ | Year |
| `month` | `` | ✅ | Month |
| `category` | `` | ✅ | Category |
| `budget_amount` | `` | ✅ | Budget Amount |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/budgets/`

예산 목록 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `year` | query | `integer` | ✅ | Year |
| `month` | query | `integer` | ✅ | Month |

**응답 `200`:** `list[BudgetResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `year` | `` | ✅ | Year |
| `month` | `` | ✅ | Month |
| `category` | `` | ✅ | Category |
| `budget_amount` | `` | ✅ | Budget Amount |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/budgets/performance`

예산 대비 실적 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `year` | query | `integer` | ✅ | Year |
| `month` | query | `integer` | ✅ | Month |

**응답 `200`:** `list[BudgetPerformanceResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `category` | `string` | ✅ | Category |
| `budget_amount` | `integer` | ✅ | Budget Amount |
| `actual_amount` | `integer` | ✅ | Actual Amount |
| `remaining` | `integer` | ✅ | Remaining |
| `usage_rate` | `number` | ✅ | Usage Rate |

---

### `PUT /api/v1/budgets/{budget_id}`

예산 수정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `budget_id` | path | `string(uuid)` | ✅ | Budget Id |

**요청 바디:** `BudgetUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `category` | `string | null` |  | Category |
| `budget_amount` | `integer | null` |  | Budget Amount |

**응답 `200`:** `BudgetResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `year` | `` | ✅ | Year |
| `month` | `` | ✅ | Month |
| `category` | `` | ✅ | Category |
| `budget_amount` | `` | ✅ | Budget Amount |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `DELETE /api/v1/budgets/{budget_id}`

예산 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `budget_id` | path | `string(uuid)` | ✅ | Budget Id |

**응답 `204`:** No Content

---

## 목표
<a id="goals"></a>

### `POST /api/v1/goals/`

목표 생성

**요청 바디:** `GoalCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `type` | `GoalType` | ✅ | 목표 유형 |
| `title` | `string` | ✅ | Title (minLen=1, maxLen=200) |
| `target_amount` | `integer` | ✅ | Target Amount (>0.0) |
| `start_date` | `string(date)` | ✅ | Start Date |
| `end_date` | `string(date)` | ✅ | End Date |
| `family_group_id` | `string(uuid) | null` |  | Family Group Id |

**응답 `201`:** `GoalResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `type` | `` | ✅ | Type |
| `title` | `` | ✅ | Title |
| `target_amount` | `` | ✅ | Target Amount |
| `current_amount` | `` | ✅ | Current Amount |
| `start_date` | `` | ✅ | Start Date |
| `end_date` | `` | ✅ | End Date |
| `status` | `` | ✅ | Status |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/goals/`

목표 목록 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `status` | query | `GoalStatus | null` |  | Status |

**응답 `200`:** `list[GoalResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `type` | `` | ✅ | Type |
| `title` | `` | ✅ | Title |
| `target_amount` | `` | ✅ | Target Amount |
| `current_amount` | `` | ✅ | Current Amount |
| `start_date` | `` | ✅ | Start Date |
| `end_date` | `` | ✅ | End Date |
| `status` | `` | ✅ | Status |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/goals/{goal_id}`

목표 상세 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `goal_id` | path | `string(uuid)` | ✅ | Goal Id |

**응답 `200`:** `GoalDetailResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `type` | `` | ✅ | Type |
| `title` | `` | ✅ | Title |
| `target_amount` | `` | ✅ | Target Amount |
| `current_amount` | `` | ✅ | Current Amount |
| `start_date` | `` | ✅ | Start Date |
| `end_date` | `` | ✅ | End Date |
| `status` | `` | ✅ | Status |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `progress_rate` | `` | ✅ | Progress Rate |

---

### `PUT /api/v1/goals/{goal_id}`

목표 수정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `goal_id` | path | `string(uuid)` | ✅ | Goal Id |

**요청 바디:** `GoalUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `title` | `string | null` |  | Title |
| `target_amount` | `integer | null` |  | Target Amount |
| `current_amount` | `integer | null` |  | Current Amount |
| `start_date` | `string(date) | null` |  | Start Date |
| `end_date` | `string(date) | null` |  | End Date |

**응답 `200`:** `GoalResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `type` | `` | ✅ | Type |
| `title` | `` | ✅ | Title |
| `target_amount` | `` | ✅ | Target Amount |
| `current_amount` | `` | ✅ | Current Amount |
| `start_date` | `` | ✅ | Start Date |
| `end_date` | `` | ✅ | End Date |
| `status` | `` | ✅ | Status |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `DELETE /api/v1/goals/{goal_id}`

목표 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `goal_id` | path | `string(uuid)` | ✅ | Goal Id |

**응답 `204`:** No Content

---

## 구독
<a id="subscriptions"></a>

### `POST /api/v1/subscriptions/`

구독 생성

**요청 바디:** `SubscriptionCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `service_name` | `string` | ✅ | Service Name (minLen=1, maxLen=100) |
| `category` | `SubscriptionCategory` | ✅ | 구독 카테고리 |
| `amount` | `integer` | ✅ | Amount (>0.0) |
| `cycle` | `SubscriptionCycle` | ✅ | 구독 결제 주기 |
| `billing_day` | `integer` | ✅ | Billing Day (min=1.0, max=31.0) |
| `asset_id` | `string(uuid) | null` |  | Asset Id |
| `start_date` | `string(date)` | ✅ | Start Date |
| `end_date` | `string(date) | null` |  | End Date |
| `status` | `SubscriptionStatus` |  | 구독 상태 |
| `notify_before_days` | `integer` |  | Notify Before Days (min=0.0, max=30.0) |
| `memo` | `string | null` |  | Memo |

**응답 `201`:** `SubscriptionResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `service_name` | `` | ✅ | Service Name |
| `category` | `` | ✅ | Category |
| `amount` | `` | ✅ | Amount |
| `cycle` | `` | ✅ | Cycle |
| `billing_day` | `` | ✅ | Billing Day |
| `asset_id` | `` | ✅ | Asset Id |
| `start_date` | `` | ✅ | Start Date |
| `end_date` | `` | ✅ | End Date |
| `status` | `` | ✅ | Status |
| `notify_before_days` | `` | ✅ | Notify Before Days |
| `memo` | `` | ✅ | Memo |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/subscriptions/`

구독 목록 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `status` | query | `SubscriptionStatus | null` |  | Status |

**응답 `200`:** `list[SubscriptionResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `service_name` | `` | ✅ | Service Name |
| `category` | `` | ✅ | Category |
| `amount` | `` | ✅ | Amount |
| `cycle` | `` | ✅ | Cycle |
| `billing_day` | `` | ✅ | Billing Day |
| `asset_id` | `` | ✅ | Asset Id |
| `start_date` | `` | ✅ | Start Date |
| `end_date` | `` | ✅ | End Date |
| `status` | `` | ✅ | Status |
| `notify_before_days` | `` | ✅ | Notify Before Days |
| `memo` | `` | ✅ | Memo |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `POST /api/v1/subscriptions/batch/notify`

결제 전 알림 배치

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `x-api-key` | header | `string` | ✅ | X-Api-Key |

**응답 `200`:** `BatchNotifyResult`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `notified_count` | `integer` | ✅ | Notified Count |
| `skipped_count` | `integer` | ✅ | Skipped Count |

---

### `POST /api/v1/subscriptions/batch/process`

구독 결제 자동 생성 배치

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `x-api-key` | header | `string` | ✅ | X-Api-Key |

**요청 바디:** `BatchProcessRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `target_date` | `string(date) | null` |  | Target Date |

**응답 `200`:** `BatchProcessResult`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `processed_count` | `integer` | ✅ | Processed Count |
| `skipped_count` | `integer` | ✅ | Skipped Count |
| `target_date` | `string(date)` | ✅ | Target Date |

---

### `GET /api/v1/subscriptions/summary`

구독 요약 조회

**응답 `200`:** `SubscriptionSummaryResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `monthly_total` | `integer` | ✅ | Monthly Total |
| `yearly_total` | `integer` | ✅ | Yearly Total |
| `active_count` | `integer` | ✅ | Active Count |

---

### `GET /api/v1/subscriptions/{subscription_id}`

구독 상세 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `subscription_id` | path | `string(uuid)` | ✅ | Subscription Id |

**응답 `200`:** `SubscriptionDetailResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `service_name` | `` | ✅ | Service Name |
| `category` | `` | ✅ | Category |
| `amount` | `` | ✅ | Amount |
| `cycle` | `` | ✅ | Cycle |
| `billing_day` | `` | ✅ | Billing Day |
| `asset_id` | `` | ✅ | Asset Id |
| `start_date` | `` | ✅ | Start Date |
| `end_date` | `` | ✅ | End Date |
| `status` | `` | ✅ | Status |
| `notify_before_days` | `` | ✅ | Notify Before Days |
| `memo` | `` | ✅ | Memo |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `next_billing_date` | `` | ✅ | Next Billing Date |

---

### `PUT /api/v1/subscriptions/{subscription_id}`

구독 수정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `subscription_id` | path | `string(uuid)` | ✅ | Subscription Id |

**요청 바디:** `SubscriptionUpdateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `service_name` | `string | null` |  | Service Name |
| `category` | `SubscriptionCategory | null` |  | 구독 카테고리 |
| `amount` | `integer | null` |  | Amount |
| `cycle` | `SubscriptionCycle | null` |  | 구독 결제 주기 |
| `billing_day` | `integer | null` |  | Billing Day |
| `asset_id` | `string(uuid) | null` |  | Asset Id |
| `start_date` | `string(date) | null` |  | Start Date |
| `end_date` | `string(date) | null` |  | End Date |
| `status` | `SubscriptionStatus | null` |  | 구독 상태 |
| `notify_before_days` | `integer | null` |  | Notify Before Days |
| `memo` | `string | null` |  | Memo |

**응답 `200`:** `SubscriptionResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `service_name` | `` | ✅ | Service Name |
| `category` | `` | ✅ | Category |
| `amount` | `` | ✅ | Amount |
| `cycle` | `` | ✅ | Cycle |
| `billing_day` | `` | ✅ | Billing Day |
| `asset_id` | `` | ✅ | Asset Id |
| `start_date` | `` | ✅ | Start Date |
| `end_date` | `` | ✅ | End Date |
| `status` | `` | ✅ | Status |
| `notify_before_days` | `` | ✅ | Notify Before Days |
| `memo` | `` | ✅ | Memo |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `DELETE /api/v1/subscriptions/{subscription_id}`

구독 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `subscription_id` | path | `string(uuid)` | ✅ | Subscription Id |

**응답 `204`:** No Content

---

## 알림
<a id="notifications"></a>

### `GET /api/v1/notifications/`

알림 목록 조회

**응답 `200`:** `list[NotificationResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `subscription_id` | `` | ✅ | Subscription Id |
| `type` | `` | ✅ | Type |
| `title` | `` | ✅ | Title |
| `message` | `` | ✅ | Message |
| `is_read` | `` | ✅ | Is Read |
| `created_at` | `` | ✅ | Created At |

---

### `PATCH /api/v1/notifications/{notification_id}/read`

알림 읽음 처리

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `notification_id` | path | `string(uuid)` | ✅ | Notification Id |

**응답 `200`:** `NotificationResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `subscription_id` | `` | ✅ | Subscription Id |
| `type` | `` | ✅ | Type |
| `title` | `` | ✅ | Title |
| `message` | `` | ✅ | Message |
| `is_read` | `` | ✅ | Is Read |
| `created_at` | `` | ✅ | Created At |

---

## 경조사 인물
<a id="ceremony-persons"></a>

### `GET /api/v1/ceremony-persons/`

경조사 인물 목록 검색

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `query` | query | `string | null` |  | 이름 또는 관계 검색어 |

**응답 `200`:** `list[CeremonyPersonResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `name` | `` | ✅ | Name |
| `relationship` | `` | ✅ | Relationship |
| `total_sent` | `` | ✅ | Total Sent |
| `total_received` | `` | ✅ | Total Received |
| `event_count` | `` | ✅ | Event Count |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/ceremony-persons/{person_id}/transactions`

특정 인물 거래 이력 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `person_id` | path | `string(uuid)` | ✅ | Person Id |

**응답 `200`:** `list[TransactionResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `date` | `` | ✅ | Date |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_category` | `` | ✅ | Minor Category |
| `description` | `` | ✅ | Description |
| `amount` | `` | ✅ | Amount |
| `discount` | `` | ✅ | Discount |
| `actual_amount` | `` | ✅ | Actual Amount |
| `asset_id` | `` | ✅ | Asset Id |
| `memo` | `` | ✅ | Memo |
| `source` | `` | ✅ | Source |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `is_private` | `` | ✅ | Is Private |

---

## 가족 카드 정산
<a id="settlement"></a>

### `GET /api/v1/settlement/calculate`

정산 계산

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `year` | query | `integer` | ✅ | Year |
| `month` | query | `integer` | ✅ | Month |
| `ratio` | query | `string | null` |  | Ratio |

**응답 `200`:** `SettlementResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `year` | `integer` | ✅ | Year |
| `month` | `integer` | ✅ | Month |
| `family_total_expense` | `integer` | ✅ | Family Total Expense |
| `split_method` | `string` | ✅ | Split Method |
| `members` | `list[MemberSettlement]` | ✅ | Members |
| `transfers` | `list[SettlementTransfer]` | ✅ | Transfers |

---

### `GET /api/v1/settlement/usage`

가족 카드 사용 현황 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `year` | query | `integer` | ✅ | Year |
| `month` | query | `integer` | ✅ | Month |

**응답 `200`:** `FamilyUsageResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `year` | `integer` | ✅ | Year |
| `month` | `integer` | ✅ | Month |
| `family_total_expense` | `integer` | ✅ | Family Total Expense |
| `members` | `list[MemberUsage]` | ✅ | Members |

---

## 통계
<a id="stats"></a>

### `GET /api/v1/stats/monthly`

월간 통계 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `year` | query | `integer` | ✅ | Year |
| `month` | query | `integer` | ✅ | Month |

**응답 `200`:** `MonthlyStatsResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `year` | `integer` | ✅ | Year |
| `month` | `integer` | ✅ | Month |
| `total_income` | `integer` | ✅ | Total Income |
| `total_expense` | `integer` | ✅ | Total Expense |
| `balance` | `integer` | ✅ | Balance |
| `category_breakdown` | `list[CategoryBreakdown]` | ✅ | Category Breakdown |
| `budget_vs_actual` | `list[BudgetVsActual]` | ✅ | Budget Vs Actual |
| `prev_month_change_rate` | `number | null` | ✅ | Prev Month Change Rate |
| `asset_breakdown` | `list[AssetBreakdown]` | ✅ | Asset Breakdown |

---

### `GET /api/v1/stats/weekly`

주간 통계 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `date` | query | `string` | ✅ | 기준 날짜 (YYYY-MM-DD 또는 ISO 8601) |

**응답 `200`:** `WeeklyStatsResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `start_date` | `string(date)` | ✅ | Start Date |
| `end_date` | `string(date)` | ✅ | End Date |
| `total_expense` | `integer` | ✅ | Total Expense |
| `daily_average` | `integer` | ✅ | Daily Average |
| `no_spend_days` | `integer` | ✅ | No Spend Days |
| `daily_expenses` | `list[DailyExpense]` | ✅ | Daily Expenses |
| `area_breakdown` | `list[AreaBreakdown]` | ✅ | Area Breakdown |

---

### `GET /api/v1/stats/yearly`

연간 통계 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `year` | query | `integer` | ✅ | Year |

**응답 `200`:** `YearlyStatsResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `year` | `integer` | ✅ | Year |
| `monthly_trends` | `list[MonthlyTrend]` | ✅ | Monthly Trends |
| `total_income` | `integer` | ✅ | Total Income |
| `total_expense` | `integer` | ✅ | Total Expense |
| `savings` | `integer` | ✅ | Savings |
| `savings_rate` | `number` | ✅ | Savings Rate |
| `top_categories` | `list[CategoryBreakdown]` | ✅ | Top Categories |
| `ceremony_summary` | `CeremonySummary` | ✅ |  |
| `subscription_summary` | `SubscriptionSummaryStats` | ✅ |  |

---

## 내보내기
<a id="export"></a>

### `GET /api/v1/export/csv`

CSV 내보내기

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `start_date` | query | `string` | ✅ | 시작일 (YYYY-MM-DD 또는 ISO 8601, 필수) |
| `end_date` | query | `string` | ✅ | 종료일 (YYYY-MM-DD 또는 ISO 8601, 필수) |
| `category` | query | `string | null` |  | 대분류 카테고리 필터 |
| `area` | query | `string | null` |  | 영역 필터 |

---

### `GET /api/v1/export/xlsx`

엑셀 내보내기

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `start_date` | query | `string` | ✅ | 시작일 (YYYY-MM-DD 또는 ISO 8601, 필수) |
| `end_date` | query | `string` | ✅ | 종료일 (YYYY-MM-DD 또는 ISO 8601, 필수) |
| `category` | query | `string | null` |  | 대분류 카테고리 필터 |
| `area` | query | `string | null` |  | 영역 필터 |

---

## 파일 업로드
<a id="upload"></a>

### `POST /api/v1/upload/profile-image-url`

프로필 이미지 업로드 Pre-signed URL 발급

**요청 바디:** `ProfileImageUploadRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `file_extension` | `string` | ✅ | File Extension |

**응답 `200`:** `PresignedUrlResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `upload_url` | `string` | ✅ | Upload Url |
| `s3_key` | `string` | ✅ | S3 Key |
| `expires_in` | `integer` |  | Expires In |

---

## AI 채팅
<a id="ai-chat"></a>

### `POST /api/v1/ai/chat/messages/{message_id}/confirm`

추출된 거래 확정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `message_id` | path | `string(uuid)` | ✅ | Message Id |

**응답 `201`:** `TransactionResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `date` | `` | ✅ | Date |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_category` | `` | ✅ | Minor Category |
| `description` | `` | ✅ | Description |
| `amount` | `` | ✅ | Amount |
| `discount` | `` | ✅ | Discount |
| `actual_amount` | `` | ✅ | Actual Amount |
| `asset_id` | `` | ✅ | Asset Id |
| `memo` | `` | ✅ | Memo |
| `source` | `` | ✅ | Source |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `is_private` | `` | ✅ | Is Private |

---

### `GET /api/v1/ai/chat/sessions`

채팅 세션 목록 조회

**응답 `200`:** `list[ChatSessionResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `title` | `` | ✅ | Title |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `POST /api/v1/ai/chat/sessions`

채팅 세션 생성

**요청 바디:** `ChatSessionCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `title` | `string | null` |  | Title |

**응답 `201`:** `ChatSessionResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `title` | `` | ✅ | Title |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/ai/chat/sessions/{session_id}`

세션 상세(메시지 목록) 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `session_id` | path | `string(uuid)` | ✅ | Session Id |

**응답 `200`:** `ChatSessionDetailResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `session` | `ChatSessionResponse` | ✅ |  |
| `messages` | `list[ChatMessageResponse]` | ✅ | Messages |

---

### `DELETE /api/v1/ai/chat/sessions/{session_id}`

세션 삭제

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `session_id` | path | `string(uuid)` | ✅ | Session Id |

**응답 `204`:** No Content

---

### `POST /api/v1/ai/chat/sessions/{session_id}/messages`

자연어 메시지 전송

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `session_id` | path | `string(uuid)` | ✅ | Session Id |

**요청 바디:** `ChatMessageRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `content` | `string` | ✅ | Content (minLen=1, maxLen=2000) |

**응답 `201`:** `ChatMessageResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `session_id` | `` | ✅ | Session Id |
| `role` | `` | ✅ | Role |
| `content` | `` | ✅ | Content |
| `extracted_data` | `` | ✅ | Extracted Data |
| `created_at` | `` | ✅ | Created At |

---

## 영수증 OCR
<a id="receipts"></a>

### `GET /api/v1/ai/receipts/`

스캔 이력 목록 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `status` | query | `string | null` |  | 스캔 상태 필터 |

**응답 `200`:** `list[ReceiptScanResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `image_url` | `` | ✅ | Image Url |
| `raw_text` | `` | ✅ | Raw Text |
| `extracted_data` | `` | ✅ | Extracted Data |
| `status` | `` | ✅ | Status |
| `transaction_id` | `` | ✅ | Transaction Id |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `POST /api/v1/ai/receipts/scan`

영수증 이미지 업로드 및 OCR

**응답 `201`:** `ReceiptScanResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `image_url` | `` | ✅ | Image Url |
| `raw_text` | `` | ✅ | Raw Text |
| `extracted_data` | `` | ✅ | Extracted Data |
| `status` | `` | ✅ | Status |
| `transaction_id` | `` | ✅ | Transaction Id |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `GET /api/v1/ai/receipts/{scan_id}`

스캔 상세 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `scan_id` | path | `string(uuid)` | ✅ | Scan Id |

**응답 `200`:** `ReceiptScanResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `image_url` | `` | ✅ | Image Url |
| `raw_text` | `` | ✅ | Raw Text |
| `extracted_data` | `` | ✅ | Extracted Data |
| `status` | `` | ✅ | Status |
| `transaction_id` | `` | ✅ | Transaction Id |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |

---

### `POST /api/v1/ai/receipts/{scan_id}/confirm`

OCR 결과 거래 확정

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `scan_id` | path | `string(uuid)` | ✅ | Scan Id |

**응답 `201`:** `TransactionResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `family_group_id` | `` | ✅ | Family Group Id |
| `date` | `` | ✅ | Date |
| `area` | `` | ✅ | Area |
| `type` | `` | ✅ | Type |
| `major_category` | `` | ✅ | Major Category |
| `minor_category` | `` | ✅ | Minor Category |
| `description` | `` | ✅ | Description |
| `amount` | `` | ✅ | Amount |
| `discount` | `` | ✅ | Discount |
| `actual_amount` | `` | ✅ | Actual Amount |
| `asset_id` | `` | ✅ | Asset Id |
| `memo` | `` | ✅ | Memo |
| `source` | `` | ✅ | Source |
| `created_at` | `` | ✅ | Created At |
| `updated_at` | `` | ✅ | Updated At |
| `is_private` | `` | ✅ | Is Private |

---

## AI 분석
<a id="ai-analysis"></a>

### `GET /api/v1/ai/analysis/monthly`

월간 지출 분석 리포트

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `year` | query | `integer` | ✅ | Year |
| `month` | query | `integer` | ✅ | Month |

**응답 `200`:** `MonthlyAnalysisResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `year` | `integer` | ✅ | Year |
| `month` | `integer` | ✅ | Month |
| `summary` | `string` | ✅ | Summary |
| `category_trends` | `list[CategoryTrend]` | ✅ | Category Trends |

---

### `GET /api/v1/ai/analysis/savings-tips`

절약 제안

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `year` | query | `integer` | ✅ | Year |
| `month` | query | `integer` | ✅ | Month |

**응답 `200`:** `SavingsTipsResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `year` | `integer` | ✅ | Year |
| `month` | `integer` | ✅ | Month |
| `over_budget_categories` | `list[OverBudgetCategory]` | ✅ | Over Budget Categories |
| `tips` | `string` | ✅ | Tips |
| `message` | `string | null` |  | Message |

---

## AI 피드백
<a id="ai-feedbacks"></a>

### `POST /api/v1/ai/feedbacks/`

피드백 제출

**요청 바디:** `FeedbackCreateRequest`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `transaction_id` | `integer` | ✅ | Transaction Id |
| `feedback_type` | `FeedbackType` | ✅ | 피드백 유형 |
| `original_value` | `string` | ✅ | Original Value (minLen=1, maxLen=200) |
| `corrected_value` | `string` | ✅ | Corrected Value (minLen=1, maxLen=200) |

**응답 `201`:** `FeedbackResponse`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `transaction_id` | `` | ✅ | Transaction Id |
| `feedback_type` | `` | ✅ | Feedback Type |
| `original_value` | `` | ✅ | Original Value |
| `corrected_value` | `` | ✅ | Corrected Value |
| `created_at` | `` | ✅ | Created At |

---

### `GET /api/v1/ai/feedbacks/`

피드백 이력 조회

**파라미터:**

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
| --- | --- | --- | :---: | --- |
| `feedback_type` | query | `string | null` |  | 피드백 유형 필터 |
| `transaction_id` | query | `integer | null` |  | 거래 ID 필터 |

**응답 `200`:** `list[FeedbackDetailResponse]`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `id` | `` | ✅ | Id |
| `user_id` | `` | ✅ | User Id |
| `transaction_id` | `` | ✅ | Transaction Id |
| `feedback_type` | `` | ✅ | Feedback Type |
| `original_value` | `` | ✅ | Original Value |
| `corrected_value` | `` | ✅ | Corrected Value |
| `created_at` | `` | ✅ | Created At |
| `transaction_description` | `` |  | Transaction Description |
| `transaction_date` | `` |  | Transaction Date |

---

