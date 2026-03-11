"""
카테고리(Category) 서비스 단위 테스트.
**Validates: Requirements 7.1~7.6, 8.3, 8.4, 8.8, 8.9, 8.11**
"""

import pytest

from app.core.exceptions import BadRequestError, ForbiddenError
from app.models.enums import Area, TransactionType
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreateRequest, CategoryUpdateRequest
from app.services.category_service import CategoryService
from tests.conftest import create_test_user


def _build_service(db_session) -> CategoryService:
    """테스트용 CategoryService 인스턴스를 생성한다."""
    repo = CategoryRepository(db_session)
    return CategoryService(repo)


# ──────────────────────────────────────────────
# 시드 데이터 생성 검증
# ──────────────────────────────────────────────


async def test_seed_defaults_creates_correct_count(db_session):
    """시드 데이터 생성 시 총 30개 카테고리가 생성되는지 검증한다.

    수입 9개 + 지출 12개 + 차계부 9개 = 30개
    """
    user = await create_test_user(db_session, email="seed-count@test.com")
    await db_session.commit()

    service = _build_service(db_session)
    created = await service.seed_defaults(user.id)

    # 전체 개수 검증
    assert len(created) == 30

    # 유형별 개수 검증
    income = [c for c in created if c.type == TransactionType.INCOME.value]
    expense_general = [
        c for c in created
        if c.type == TransactionType.EXPENSE.value and c.area == Area.GENERAL.value
    ]
    expense_car = [
        c for c in created
        if c.type == TransactionType.EXPENSE.value and c.area == Area.CAR.value
    ]

    assert len(income) == 9
    assert len(expense_general) == 12
    assert len(expense_car) == 9


async def test_seed_defaults_all_is_default_true(db_session):
    """시드 데이터로 생성된 모든 카테고리의 is_default가 True인지 검증한다."""
    user = await create_test_user(db_session, email="seed-default@test.com")
    await db_session.commit()

    service = _build_service(db_session)
    created = await service.seed_defaults(user.id)

    for category in created:
        assert category.is_default is True, (
            f"카테고리 '{category.major_category}'의 is_default가 False입니다"
        )


async def test_seed_defaults_sort_order_sequential(db_session):
    """시드 데이터의 sort_order가 유형별로 순차적으로 할당되는지 검증한다.

    수입: 1~9, 지출(일반): 1~12, 지출(차계부): 1~9
    """
    user = await create_test_user(db_session, email="seed-sort@test.com")
    await db_session.commit()

    service = _build_service(db_session)
    created = await service.seed_defaults(user.id)

    # 수입 카테고리 sort_order 검증
    income = [c for c in created if c.type == TransactionType.INCOME.value]
    income_orders = sorted(c.sort_order for c in income)
    assert income_orders == list(range(1, 10))

    # 지출(일반) 카테고리 sort_order 검증
    expense_general = [
        c for c in created
        if c.type == TransactionType.EXPENSE.value and c.area == Area.GENERAL.value
    ]
    expense_general_orders = sorted(c.sort_order for c in expense_general)
    assert expense_general_orders == list(range(1, 13))

    # 지출(차계부) 카테고리 sort_order 검증
    expense_car = [
        c for c in created
        if c.type == TransactionType.EXPENSE.value and c.area == Area.CAR.value
    ]
    expense_car_orders = sorted(c.sort_order for c in expense_car)
    assert expense_car_orders == list(range(1, 10))


# ──────────────────────────────────────────────
# 기본 카테고리 보호 검증
# ──────────────────────────────────────────────


async def test_update_default_category_name_rejected(db_session):
    """기본 카테고리(is_default=True)의 이름 변경 시 BadRequestError가 발생하는지 검증한다."""
    user = await create_test_user(db_session, email="update-reject@test.com")
    await db_session.commit()

    service = _build_service(db_session)
    created = await service.seed_defaults(user.id)

    # 첫 번째 기본 카테고리의 이름 변경 시도
    target = created[0]
    update_data = CategoryUpdateRequest(major_category="변경된이름")

    with pytest.raises(BadRequestError):
        await service.update(user, target.id, update_data)


async def test_delete_default_category_rejected(db_session):
    """기본 카테고리(is_default=True) 삭제 시 BadRequestError가 발생하는지 검증한다."""
    user = await create_test_user(db_session, email="delete-reject@test.com")
    await db_session.commit()

    service = _build_service(db_session)
    created = await service.seed_defaults(user.id)

    # 첫 번째 기본 카테고리 삭제 시도
    target = created[0]

    with pytest.raises(BadRequestError):
        await service.delete(user, target.id)


# ──────────────────────────────────────────────
# 소유권 검증
# ──────────────────────────────────────────────


async def test_update_category_forbidden_for_other_user(db_session):
    """다른 사용자의 카테고리 수정 시 ForbiddenError가 발생하는지 검증한다."""
    user_a = await create_test_user(db_session, email="owner-cat@test.com")
    user_b = await create_test_user(db_session, email="other-cat@test.com")
    await db_session.commit()

    service = _build_service(db_session)

    # user_a의 커스텀 카테고리 생성
    category = await service.create(
        user_a,
        CategoryCreateRequest(
            area=Area.GENERAL,
            type=TransactionType.EXPENSE,
            major_category="테스트카테고리",
        ),
    )

    # user_b가 user_a의 카테고리 수정 시도
    update_data = CategoryUpdateRequest(major_category="변경시도")

    with pytest.raises(ForbiddenError):
        await service.update(user_b, category.id, update_data)
