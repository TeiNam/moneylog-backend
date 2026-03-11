"""
GoalService 단위 테스트 및 속성 기반 테스트.

목표 CRUD, 상태 필터링, 진행률 계산, 자동 완료/실패, 권한 검증을 검증한다.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.enums import GoalStatus, GoalType
from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import GoalCreateRequest, GoalUpdateRequest
from app.services.goal_service import GoalService
from tests.conftest import create_test_user

# Hypothesis 전략 정의
goal_types = st.sampled_from([GoalType.MONTHLY_SAVING, GoalType.SAVING_RATE, GoalType.SPECIAL])
target_amounts = st.integers(min_value=1, max_value=100_000_000)
current_amounts = st.integers(min_value=0, max_value=100_000_000)
titles = st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=("L", "N")))


# ══════════════════════════════════════════════
# 단위 테스트
# ══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_goal(db_session):
    """목표 생성 정상 동작 검증."""
    user = await create_test_user(db_session)
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    data = GoalCreateRequest(
        type=GoalType.MONTHLY_SAVING,
        title="월 100만원 저축",
        target_amount=1_000_000,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    goal = await service.create(user, data)

    assert goal.user_id == user.id
    assert goal.type == GoalType.MONTHLY_SAVING.value
    assert goal.title == "월 100만원 저축"
    assert goal.target_amount == 1_000_000
    assert goal.current_amount == 0
    assert goal.status == GoalStatus.ACTIVE.value
    assert goal.created_at is not None


@pytest.mark.asyncio
async def test_get_list_with_status_filter(db_session):
    """상태 필터링 검증."""
    user = await create_test_user(db_session)
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    # ACTIVE 목표 2개 생성
    await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING, title="목표1",
            target_amount=1_000_000, start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        ),
    )
    goal2 = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.SPECIAL, title="목표2",
            target_amount=500_000, start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        ),
    )

    # goal2를 COMPLETED로 변경
    await repo.update(goal2.id, {"status": GoalStatus.COMPLETED.value})

    # ACTIVE 필터
    active_goals = await service.get_list(user, status=GoalStatus.ACTIVE)
    assert len(active_goals) == 1
    assert all(g.status == GoalStatus.ACTIVE.value for g in active_goals)

    # COMPLETED 필터
    completed_goals = await service.get_list(user, status=GoalStatus.COMPLETED)
    assert len(completed_goals) == 1
    assert all(g.status == GoalStatus.COMPLETED.value for g in completed_goals)

    # 필터 없이 전체 조회
    all_goals = await service.get_list(user)
    assert len(all_goals) == 2


@pytest.mark.asyncio
async def test_get_detail_progress_rate(db_session):
    """진행률 계산 검증."""
    user = await create_test_user(db_session)
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING, title="저축 목표",
            target_amount=1_000_000, start_date=date(2025, 1, 1), end_date=date(2030, 12, 31),
        ),
    )

    # current_amount를 300000으로 설정
    await repo.update(goal.id, {"current_amount": 300_000})

    detail = await service.get_detail(user, goal.id)
    assert detail.progress_rate == 30.0  # 300000 / 1000000 * 100


@pytest.mark.asyncio
async def test_auto_completion_on_update(db_session):
    """자동 완료 (current_amount >= target_amount) 검증."""
    user = await create_test_user(db_session)
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING, title="저축 목표",
            target_amount=1_000_000, start_date=date(2025, 1, 1), end_date=date(2030, 12, 31),
        ),
    )

    # current_amount를 target_amount 이상으로 수정
    updated = await service.update(
        user, goal.id, GoalUpdateRequest(current_amount=1_000_000)
    )
    assert updated.status == GoalStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_auto_failure_on_expiration(db_session):
    """만료 목표 자동 실패 검증."""
    user = await create_test_user(db_session)
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    # 이미 만료된 목표 생성
    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING, title="만료 목표",
            target_amount=1_000_000, start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
        ),
    )

    # date.today()를 만료일 이후로 모킹
    with patch("app.services.goal_service.date") as mock_date:
        mock_date.today.return_value = date(2025, 6, 1)
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        detail = await service.get_detail(user, goal.id)
        assert detail.status == GoalStatus.FAILED.value


@pytest.mark.asyncio
async def test_cannot_update_completed_goal(db_session):
    """COMPLETED 목표 수정 불가 검증."""
    user = await create_test_user(db_session)
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING, title="완료 목표",
            target_amount=1_000_000, start_date=date(2025, 1, 1), end_date=date(2030, 12, 31),
        ),
    )

    # COMPLETED로 변경
    await repo.update(goal.id, {"status": GoalStatus.COMPLETED.value})

    with pytest.raises(BadRequestError):
        await service.update(user, goal.id, GoalUpdateRequest(title="수정 시도"))


@pytest.mark.asyncio
async def test_cannot_update_failed_goal(db_session):
    """FAILED 목표 수정 불가 검증."""
    user = await create_test_user(db_session)
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING, title="실패 목표",
            target_amount=1_000_000, start_date=date(2025, 1, 1), end_date=date(2030, 12, 31),
        ),
    )

    # FAILED로 변경
    await repo.update(goal.id, {"status": GoalStatus.FAILED.value})

    with pytest.raises(BadRequestError):
        await service.update(user, goal.id, GoalUpdateRequest(current_amount=500_000))


@pytest.mark.asyncio
async def test_forbidden_error_on_other_user(db_session):
    """권한 없는 접근 시 ForbiddenError 검증."""
    user_a = await create_test_user(db_session, email="goal_a@test.com", nickname="A")
    user_b = await create_test_user(db_session, email="goal_b@test.com", nickname="B")
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    goal = await service.create(
        user_a,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING, title="A의 목표",
            target_amount=1_000_000, start_date=date(2025, 1, 1), end_date=date(2030, 12, 31),
        ),
    )

    # B가 A의 목표 상세 조회 시도
    with pytest.raises(ForbiddenError):
        await service.get_detail(user_b, goal.id)

    # B가 A의 목표 수정 시도
    with pytest.raises(ForbiddenError):
        await service.update(user_b, goal.id, GoalUpdateRequest(title="수정"))

    # B가 A의 목표 삭제 시도
    with pytest.raises(ForbiddenError):
        await service.delete(user_b, goal.id)


@pytest.mark.asyncio
async def test_not_found_error_on_nonexistent(db_session):
    """존재하지 않는 목표 접근 시 NotFoundError 검증."""
    user = await create_test_user(db_session)
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    fake_id = uuid.uuid4()

    with pytest.raises(NotFoundError):
        await service.get_detail(user, fake_id)

    with pytest.raises(NotFoundError):
        await service.update(user, fake_id, GoalUpdateRequest(title="수정"))

    with pytest.raises(NotFoundError):
        await service.delete(user, fake_id)



# ══════════════════════════════════════════════
# 속성 기반 테스트 (Property-Based Tests)
# ══════════════════════════════════════════════


# ──────────────────────────────────────────────
# Property 8: 목표 생성 라운드트립
# Feature: moneylog-backend-phase5, Property 8: 목표 생성 라운드트립
# Validates: Requirements 2.1, 5.1, 5.2, 5.3
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    goal_type=goal_types,
    title=titles,
    amount=target_amounts,
)
async def test_property_goal_create_roundtrip(db_session, goal_type, title, amount):
    """유효한 목표 데이터에 대해, create 후 모든 필드가 입력과 일치하고 status=ACTIVE, current_amount=0이어야 한다."""
    user = await create_test_user(
        db_session, email=f"p8_{uuid.uuid4().hex[:8]}@test.com", nickname="P8"
    )
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    data = GoalCreateRequest(
        type=goal_type,
        title=title,
        target_amount=amount,
        start_date=date(2025, 1, 1),
        end_date=date(2030, 12, 31),
    )
    goal = await service.create(user, data)

    # 모든 필드 일치 검증
    assert goal.user_id == user.id
    assert goal.type == goal_type.value
    assert goal.title == title
    assert goal.target_amount == amount
    assert goal.current_amount == 0
    assert goal.status == GoalStatus.ACTIVE.value
    assert goal.start_date == date(2025, 1, 1)
    assert goal.end_date == date(2030, 12, 31)
    assert goal.created_at is not None


# ──────────────────────────────────────────────
# Property 9: 목표 목록 상태 필터링
# Feature: moneylog-backend-phase5, Property 9: 목표 목록 상태 필터링
# Validates: Requirements 5.4, 5.5
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    filter_status=st.sampled_from([GoalStatus.ACTIVE, GoalStatus.COMPLETED, GoalStatus.FAILED]),
)
async def test_property_goal_list_status_filter(db_session, filter_status):
    """다양한 상태의 목표에서 status 필터 적용 시 해당 상태만 반환되어야 한다."""
    user = await create_test_user(
        db_session, email=f"p9_{uuid.uuid4().hex[:8]}@test.com", nickname="P9"
    )
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    # 각 상태별 목표 1개씩 생성
    for status in [GoalStatus.ACTIVE, GoalStatus.COMPLETED, GoalStatus.FAILED]:
        goal = await service.create(
            user,
            GoalCreateRequest(
                type=GoalType.MONTHLY_SAVING,
                title=f"목표_{status.value}",
                target_amount=1_000_000,
                start_date=date(2025, 1, 1),
                end_date=date(2030, 12, 31),
            ),
        )
        # ACTIVE가 아닌 상태는 직접 설정
        if status != GoalStatus.ACTIVE:
            await repo.update(goal.id, {"status": status.value})

    # 필터 적용
    result = await service.get_list(user, status=filter_status)

    # 반환된 모든 목표의 status가 필터 값과 일치
    assert len(result) >= 1
    for g in result:
        assert g.status == filter_status.value
        assert g.user_id == user.id


# ──────────────────────────────────────────────
# Property 10: 목표 진행률 계산
# Feature: moneylog-backend-phase5, Property 10: 목표 진행률 계산
# Validates: Requirements 5.6
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    target_amt=target_amounts,
    current_amt=current_amounts,
)
async def test_property_goal_progress_rate(db_session, target_amt, current_amt):
    """목표 상세 조회 시 progress_rate = current_amount / target_amount * 100 이어야 한다."""
    user = await create_test_user(
        db_session, email=f"p10_{uuid.uuid4().hex[:8]}@test.com", nickname="P10"
    )
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING,
            title="진행률 테스트",
            target_amount=target_amt,
            start_date=date(2025, 1, 1),
            end_date=date(2030, 12, 31),
        ),
    )

    # current_amount 설정 (자동 완료 방지를 위해 target_amt 미만으로 제한)
    safe_current = current_amt % target_amt  # 0 ~ target_amt-1 범위
    await repo.update(goal.id, {"current_amount": safe_current})

    detail = await service.get_detail(user, goal.id)

    expected_rate = round(safe_current / target_amt * 100, 1)
    assert detail.progress_rate == expected_rate


# ──────────────────────────────────────────────
# Property 11: 목표 자동 완료
# Feature: moneylog-backend-phase5, Property 11: 목표 자동 완료
# Validates: Requirements 6.1
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    target_amt=st.integers(min_value=1, max_value=10_000_000),
)
async def test_property_goal_auto_completion(db_session, target_amt):
    """ACTIVE 목표에서 current_amount >= target_amount 설정 시 status가 COMPLETED로 변경되어야 한다."""
    user = await create_test_user(
        db_session, email=f"p11_{uuid.uuid4().hex[:8]}@test.com", nickname="P11"
    )
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING,
            title="자동 완료 테스트",
            target_amount=target_amt,
            start_date=date(2025, 1, 1),
            end_date=date(2030, 12, 31),
        ),
    )

    # current_amount를 target_amount 이상으로 수정
    updated = await service.update(
        user, goal.id, GoalUpdateRequest(current_amount=target_amt)
    )

    assert updated.status == GoalStatus.COMPLETED.value


# ──────────────────────────────────────────────
# Property 12: 만료 목표 자동 실패
# Feature: moneylog-backend-phase5, Property 12: 만료 목표 자동 실패
# Validates: Requirements 6.2
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    days_past=st.integers(min_value=1, max_value=365),
)
async def test_property_goal_auto_failure_on_expiration(db_session, days_past):
    """ACTIVE 목표에서 end_date < today이면 get_detail 시 status가 FAILED로 변경되어야 한다."""
    user = await create_test_user(
        db_session, email=f"p12_{uuid.uuid4().hex[:8]}@test.com", nickname="P12"
    )
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    # 기준일: 2025-06-01
    base_date = date(2025, 6, 1)
    end_date = base_date - timedelta(days=days_past)

    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING,
            title="만료 테스트",
            target_amount=1_000_000,
            start_date=date(2020, 1, 1),
            end_date=end_date,
        ),
    )

    # date.today()를 base_date로 모킹 (end_date 이후)
    with patch("app.services.goal_service.date") as mock_date:
        mock_date.today.return_value = base_date
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        detail = await service.get_detail(user, goal.id)
        assert detail.status == GoalStatus.FAILED.value


# ──────────────────────────────────────────────
# Property 13: 완료/실패 목표 수정 불가
# Feature: moneylog-backend-phase5, Property 13: 완료/실패 목표 수정 불가
# Validates: Requirements 6.3, 6.4
# ──────────────────────────────────────────────


@pytest.mark.asyncio
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    terminal_status=st.sampled_from([GoalStatus.COMPLETED, GoalStatus.FAILED]),
    new_amount=current_amounts,
)
async def test_property_goal_immutable_when_terminal(db_session, terminal_status, new_amount):
    """COMPLETED 또는 FAILED 상태의 목표 수정 시 BadRequestError가 발생해야 한다."""
    user = await create_test_user(
        db_session, email=f"p13_{uuid.uuid4().hex[:8]}@test.com", nickname="P13"
    )
    repo = GoalRepository(db_session)
    service = GoalService(repo)

    goal = await service.create(
        user,
        GoalCreateRequest(
            type=GoalType.MONTHLY_SAVING,
            title="수정 불가 테스트",
            target_amount=1_000_000,
            start_date=date(2025, 1, 1),
            end_date=date(2030, 12, 31),
        ),
    )

    # 상태를 COMPLETED 또는 FAILED로 직접 변경
    await repo.update(goal.id, {"status": terminal_status.value})

    # 수정 시도 → BadRequestError
    with pytest.raises(BadRequestError):
        await service.update(
            user, goal.id, GoalUpdateRequest(current_amount=new_amount)
        )
