"""
알림 조회 및 읽음 처리 속성 기반 테스트.

Property 18: 알림 목록 정렬 (created_at 내림차순)
Property 19: 알림 읽음 처리 라운드트립
Property 20: 알림 접근 권한 검증
"""

import asyncio
import pytest
from datetime import date
from uuid import uuid4

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.core.exceptions import ForbiddenError
from app.models.enums import SubscriptionCategory, SubscriptionCycle, SubscriptionStatus
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.subscription_service import SubscriptionService
from app.schemas.subscription import SubscriptionCreateRequest
from tests.conftest import create_test_user


# ──────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────

async def _create_subscription_direct(repo, user_id, **overrides):
    """구독을 직접 리포지토리로 생성하는 헬퍼."""
    defaults = {
        "user_id": user_id,
        "service_name": "TestService",
        "category": "OTT",
        "amount": 10000,
        "cycle": "MONTHLY",
        "billing_day": 15,
        "start_date": date(2025, 1, 1),
        "status": "ACTIVE",
        "notify_before_days": 1,
    }
    defaults.update(overrides)
    return await repo.create(defaults)


async def _create_notification_direct(repo, user_id, subscription_id, **overrides):
    """알림을 직접 리포지토리로 생성하는 헬퍼."""
    defaults = {
        "user_id": user_id,
        "subscription_id": subscription_id,
        "type": "SUBSCRIPTION_PAYMENT",
        "title": "구독 결제 예정",
        "message": "테스트 알림",
        "is_read": False,
    }
    defaults.update(overrides)
    return await repo.create(defaults)


# ──────────────────────────────────────────────
# Property 18: 알림 목록 정렬
# Feature: moneylog-backend-phase4, Property 18: 알림 목록 정렬
# Validates: Requirements 8.1
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    count=st.integers(min_value=2, max_value=5),
)
async def test_property_notification_list_sorted_desc(db_session, count):
    """사용자의 알림 목록은 항상 created_at 내림차순(최신순)으로 정렬되어야 한다."""
    user = await create_test_user(
        db_session, email=f"p18_{uuid4().hex[:8]}@test.com", nickname="P18"
    )
    sub_repo = SubscriptionRepository(db_session)
    noti_repo = NotificationRepository(db_session)
    service = SubscriptionService(sub_repo, notification_repo=noti_repo)

    # 구독 생성
    sub = await _create_subscription_direct(sub_repo, user.id)

    # 여러 알림을 순차적으로 생성 (created_at이 자동 설정됨)
    for i in range(count):
        await _create_notification_direct(
            noti_repo, user.id, sub.id, message=f"알림 {i}"
        )
        # SQLite에서 created_at 차이를 보장하기 위해 짧은 대기
        await asyncio.sleep(0.01)

    # 알림 목록 조회
    notifications = await service.get_notifications(user)

    # created_at 내림차순 정렬 검증
    assert len(notifications) == count
    for i in range(len(notifications) - 1):
        assert notifications[i].created_at >= notifications[i + 1].created_at


# ──────────────────────────────────────────────
# Property 19: 알림 읽음 처리 라운드트립
# Feature: moneylog-backend-phase4, Property 19: 알림 읽음 처리 라운드트립
# Validates: Requirements 8.2
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    data=st.data(),
)
async def test_property_mark_notification_read_roundtrip(db_session, data):
    """알림 생성 후 읽음 처리하면 is_read가 True여야 한다."""
    user = await create_test_user(
        db_session, email=f"p19_{uuid4().hex[:8]}@test.com", nickname="P19"
    )
    sub_repo = SubscriptionRepository(db_session)
    noti_repo = NotificationRepository(db_session)
    service = SubscriptionService(sub_repo, notification_repo=noti_repo)

    # 구독 및 알림 생성
    sub = await _create_subscription_direct(sub_repo, user.id)
    notification = await _create_notification_direct(noti_repo, user.id, sub.id)

    # 생성 직후 is_read는 False
    assert notification.is_read is False

    # 읽음 처리
    updated = await service.mark_notification_read(user, notification.id)

    # 읽음 처리 후 is_read는 True
    assert updated.is_read is True


# ──────────────────────────────────────────────
# Property 20: 알림 접근 권한 검증
# Feature: moneylog-backend-phase4, Property 20: 알림 접근 권한 검증
# Validates: Requirements 8.3
# ──────────────────────────────────────────────

@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    data=st.data(),
)
async def test_property_notification_permission_check(db_session, data):
    """User B가 User A의 알림을 읽음 처리하면 ForbiddenError가 발생해야 한다."""
    user_a = await create_test_user(
        db_session, email=f"p20a_{uuid4().hex[:8]}@test.com", nickname="A20"
    )
    user_b = await create_test_user(
        db_session, email=f"p20b_{uuid4().hex[:8]}@test.com", nickname="B20"
    )
    sub_repo = SubscriptionRepository(db_session)
    noti_repo = NotificationRepository(db_session)
    service = SubscriptionService(sub_repo, notification_repo=noti_repo)

    # User A의 구독 및 알림 생성
    sub = await _create_subscription_direct(sub_repo, user_a.id)
    notification = await _create_notification_direct(noti_repo, user_a.id, sub.id)

    # User B가 User A의 알림을 읽음 처리 시도 → ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.mark_notification_read(user_b, notification.id)
