"""
카테고리(Category) 비즈니스 로직 서비스.

카테고리 시드 데이터 생성, CRUD, 정렬 순서 변경을 담당한다.
기본 카테고리 보호(이름 변경/삭제 거부) 및 소유권 검증을 수행한다.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.category_config import CategoryConfig
from app.models.enums import Area, OwnerType, TransactionType
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
    SortOrderItem,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 기본 카테고리 시드 데이터 정의
# ──────────────────────────────────────────────

# 일반 영역 - 수입 카테고리
_DEFAULT_INCOME_CATEGORIES: list[dict] = [
    {"name": "이월", "icon": "🔄", "color": "#4CAF50"},
    {"name": "급여", "icon": "💰", "color": "#2196F3"},
    {"name": "수당", "icon": "💵", "color": "#03A9F4"},
    {"name": "상여", "icon": "🎁", "color": "#00BCD4"},
    {"name": "투자수익", "icon": "📈", "color": "#009688"},
    {"name": "이자", "icon": "🏦", "color": "#4DB6AC"},
    {"name": "부수익", "icon": "💸", "color": "#66BB6A"},
    {"name": "처분소득", "icon": "🏷️", "color": "#8BC34A"},
    {"name": "기타수입", "icon": "📥", "color": "#CDDC39"},
]

# 일반 영역 - 지출 카테고리 (소분류 포함)
_DEFAULT_EXPENSE_CATEGORIES: list[dict] = [
    {"name": "식비", "icon": "🍚", "color": "#FF5722", "minor": ["배달/외식", "식료품", "간식/음료", "카페"]},
    {"name": "주거비", "icon": "🏠", "color": "#795548", "minor": ["월세", "관리비", "수도/전기/가스"]},
    {"name": "생활용품비", "icon": "🧹", "color": "#607D8B", "minor": ["세제/청소", "주방용품", "생활잡화"]},
    {"name": "반려동물비", "icon": "🐾", "color": "#FF9800", "minor": ["사료/간식", "병원/약", "용품"]},
    {"name": "의류미용비", "icon": "👗", "color": "#E91E63", "minor": ["의류", "미용실", "화장품"]},
    {"name": "교육비", "icon": "📚", "color": "#3F51B5", "minor": ["학원/과외", "교재/도서", "온라인강의"]},
    {"name": "문화생활비", "icon": "🎬", "color": "#9C27B0", "minor": ["영화/공연", "여행", "취미/운동"]},
    {"name": "의료비", "icon": "🏥", "color": "#F44336", "minor": ["병원", "약국", "건강검진"]},
    {"name": "유류교통비", "icon": "🚌", "color": "#FF9800", "minor": ["대중교통", "택시", "주유"]},
    {"name": "통신비", "icon": "📱", "color": "#2196F3", "minor": ["휴대폰", "인터넷", "구독서비스"]},
    {"name": "경조사회비", "icon": "🎊", "color": "#673AB7", "minor": ["축의금", "부의금", "선물"]},
    {"name": "용돈", "icon": "💳", "color": "#FFC107", "minor": ["부모님", "자녀", "기타"]},
]

# 차계부 영역 - 지출 카테고리
_DEFAULT_CAR_CATEGORIES: list[dict] = [
    {"name": "유류비/충전비", "icon": "⛽", "color": "#FF5722"},
    {"name": "정비/수리", "icon": "🔧", "color": "#795548"},
    {"name": "보험", "icon": "🛡️", "color": "#2196F3"},
    {"name": "세금", "icon": "📋", "color": "#607D8B"},
    {"name": "할부", "icon": "💳", "color": "#9C27B0"},
    {"name": "톨비", "icon": "🛣️", "color": "#4CAF50"},
    {"name": "주차", "icon": "🅿️", "color": "#00BCD4"},
    {"name": "세차", "icon": "🚿", "color": "#03A9F4"},
    {"name": "기타", "icon": "📦", "color": "#9E9E9E"},
]


class CategoryService:
    """카테고리 CRUD 및 시드 데이터 관리 서비스."""

    def __init__(self, repo: CategoryRepository) -> None:
        self._repo = repo

    # ──────────────────────────────────────────────
    # 기본 카테고리 시드 생성
    # ──────────────────────────────────────────────

    async def seed_defaults(self, user_id: UUID) -> list[CategoryConfig]:
        """회원가입 시 기본 수입/지출/차계부 카테고리를 생성한다.

        Args:
            user_id: 새로 가입한 사용자 ID

        Returns:
            생성된 기본 카테고리 목록
        """
        created: list[CategoryConfig] = []
        sort_order = 1

        # 일반 영역 - 수입 카테고리
        for cat in _DEFAULT_INCOME_CATEGORIES:
            category = await self._repo.create({
                "owner_id": user_id,
                "owner_type": OwnerType.USER.value,
                "area": Area.GENERAL.value,
                "type": TransactionType.INCOME.value,
                "major_category": cat["name"],
                "minor_categories": [],
                "icon": cat["icon"],
                "color": cat["color"],
                "is_default": True,
                "is_active": True,
                "sort_order": sort_order,
            })
            created.append(category)
            sort_order += 1

        # 일반 영역 - 지출 카테고리 (소분류 포함)
        sort_order = 1
        for cat in _DEFAULT_EXPENSE_CATEGORIES:
            category = await self._repo.create({
                "owner_id": user_id,
                "owner_type": OwnerType.USER.value,
                "area": Area.GENERAL.value,
                "type": TransactionType.EXPENSE.value,
                "major_category": cat["name"],
                "minor_categories": cat.get("minor", []),
                "icon": cat["icon"],
                "color": cat["color"],
                "is_default": True,
                "is_active": True,
                "sort_order": sort_order,
            })
            created.append(category)
            sort_order += 1

        # 차계부 영역 - 지출 카테고리
        sort_order = 1
        for cat in _DEFAULT_CAR_CATEGORIES:
            category = await self._repo.create({
                "owner_id": user_id,
                "owner_type": OwnerType.USER.value,
                "area": Area.CAR.value,
                "type": TransactionType.EXPENSE.value,
                "major_category": cat["name"],
                "minor_categories": [],
                "icon": cat["icon"],
                "color": cat["color"],
                "is_default": True,
                "is_active": True,
                "sort_order": sort_order,
            })
            created.append(category)
            sort_order += 1

        logger.info(
            "기본 카테고리 시드 생성 완료: user_id=%s, 총 %d개",
            user_id,
            len(created),
        )
        return created

    # ──────────────────────────────────────────────
    # 카테고리 생성
    # ──────────────────────────────────────────────

    async def create(
        self, user: User, data: CategoryCreateRequest
    ) -> CategoryConfig:
        """새 대분류 카테고리를 생성한다.

        Args:
            user: 현재 인증된 사용자
            data: 카테고리 생성 요청 데이터

        Returns:
            생성된 CategoryConfig 객체
        """
        # 현재 최대 sort_order 조회 후 +1
        max_sort = await self._repo.get_max_sort_order(
            owner_id=user.id,
            owner_type=OwnerType.USER.value,
            area=data.area.value,
            type=data.type.value,
        )

        category = await self._repo.create({
            "owner_id": user.id,
            "owner_type": OwnerType.USER.value,
            "area": data.area.value,
            "type": data.type.value,
            "major_category": data.major_category,
            "minor_categories": data.minor_categories,
            "icon": data.icon,
            "color": data.color,
            "is_default": False,
            "is_active": True,
            "sort_order": max_sort + 1,
        })

        logger.info("카테고리 생성 완료: category_id=%s", category.id)
        return category

    # ──────────────────────────────────────────────
    # 카테고리 목록 조회
    # ──────────────────────────────────────────────

    async def get_list(
        self,
        user: User,
        area: Area | None = None,
        type: TransactionType | None = None,
    ) -> list[CategoryConfig]:
        """사용자의 카테고리 목록을 필터링하여 반환한다.

        Args:
            user: 현재 인증된 사용자
            area: 거래 영역 필터 (선택)
            type: 거래 유형 필터 (선택)

        Returns:
            sort_order 오름차순으로 정렬된 카테고리 목록
        """
        return await self._repo.get_list(
            owner_id=user.id,
            owner_type=OwnerType.USER.value,
            area=area.value if area else None,
            type=type.value if type else None,
        )

    # ──────────────────────────────────────────────
    # 카테고리 수정
    # ──────────────────────────────────────────────

    async def update(
        self,
        user: User,
        category_id: UUID,
        data: CategoryUpdateRequest,
    ) -> CategoryConfig:
        """카테고리를 수정한다.

        기본 카테고리(is_default=True)의 이름 변경은 거부하지만,
        아이콘/색상/소분류/활성화 상태 변경은 허용한다.

        Args:
            user: 현재 인증된 사용자
            category_id: 수정할 카테고리 ID
            data: 카테고리 수정 요청 데이터

        Returns:
            갱신된 CategoryConfig 객체

        Raises:
            NotFoundError: 카테고리가 존재하지 않을 때
            ForbiddenError: 소유권이 없을 때
            BadRequestError: 기본 카테고리 이름 변경 시도 시
        """
        category = await self._repo.get_by_id(category_id)
        if category is None:
            raise NotFoundError("카테고리를 찾을 수 없습니다")

        self._check_ownership(user, category)

        # 기본 카테고리 이름 변경 거부
        if category.is_default and data.major_category is not None:
            raise BadRequestError("기본 카테고리의 이름은 변경할 수 없습니다")

        # None이 아닌 필드만 업데이트 딕셔너리에 포함
        update_data: dict = {}
        for field in ("major_category", "minor_categories", "icon", "color", "is_active"):
            value = getattr(data, field, None)
            if value is not None:
                update_data[field] = value

        # updated_at 설정
        update_data["updated_at"] = datetime.now(timezone.utc)

        updated = await self._repo.update(category_id, update_data)
        logger.info("카테고리 수정 완료: category_id=%s", category_id)
        return updated

    # ──────────────────────────────────────────────
    # 카테고리 삭제
    # ──────────────────────────────────────────────

    async def delete(self, user: User, category_id: UUID) -> None:
        """카테고리를 삭제한다.

        기본 카테고리(is_default=True)는 삭제할 수 없다.

        Args:
            user: 현재 인증된 사용자
            category_id: 삭제할 카테고리 ID

        Raises:
            NotFoundError: 카테고리가 존재하지 않을 때
            ForbiddenError: 소유권이 없을 때
            BadRequestError: 기본 카테고리 삭제 시도 시
        """
        category = await self._repo.get_by_id(category_id)
        if category is None:
            raise NotFoundError("카테고리를 찾을 수 없습니다")

        self._check_ownership(user, category)

        if category.is_default:
            raise BadRequestError("기본 카테고리는 삭제할 수 없습니다")

        await self._repo.delete(category_id)
        logger.info("카테고리 삭제 완료: category_id=%s", category_id)

    # ──────────────────────────────────────────────
    # 정렬 순서 일괄 변경
    # ──────────────────────────────────────────────

    async def update_sort_order(
        self, user: User, items: list[SortOrderItem]
    ) -> None:
        """카테고리 정렬 순서를 일괄 변경한다.

        Args:
            user: 현재 인증된 사용자
            items: 정렬 순서 변경 항목 목록
        """
        sort_data = [
            {"id": item.id, "sort_order": item.sort_order}
            for item in items
        ]
        await self._repo.bulk_update_sort_order(sort_data)
        logger.info("카테고리 정렬 순서 변경 완료: %d건", len(items))

    # ──────────────────────────────────────────────
    # 소유권 검증
    # ──────────────────────────────────────────────

    def _check_ownership(self, user: User, category: CategoryConfig) -> None:
        """사용자가 해당 카테고리의 소유자인지 검증한다.

        본인 소유(USER)이거나, 소속 가족 그룹(FAMILY_GROUP) 소유인 경우 허용한다.

        Raises:
            ForbiddenError: 소유권이 없을 때
        """
        # 사용자 본인 소유 확인
        if (
            category.owner_type == OwnerType.USER.value
            and category.owner_id == user.id
        ):
            return

        # 소속 가족 그룹 소유 확인
        if (
            category.owner_type == OwnerType.FAMILY_GROUP.value
            and user.family_group_id is not None
            and category.owner_id == user.family_group_id
        ):
            return

        raise ForbiddenError("해당 카테고리에 대한 접근 권한이 없습니다")
