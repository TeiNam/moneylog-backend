"""UTC datetime 직렬화 테스트.

모든 응답 스키마의 datetime 필드가 ISO 8601 UTC(Z 접미사) 형식으로
직렬화되는지 검증한다.

Validates: Requirements 4.5
"""

import importlib
import inspect
import pkgutil
from datetime import datetime, timezone

from pydantic import BaseModel

import app.schemas as schemas_pkg
from app.schemas.common import UTCDatetimeResponse


def _get_all_response_schemas() -> list[type[BaseModel]]:
    """app/schemas 패키지에서 datetime 필드를 가진 모든 응답 스키마를 수집한다."""
    result = []
    for _importer, modname, _ispkg in pkgutil.iter_modules(schemas_pkg.__path__):
        module = importlib.import_module(f"app.schemas.{modname}")
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            # Pydantic BaseModel 서브클래스만 대상
            if not issubclass(cls, BaseModel) or cls is BaseModel:
                continue
            # "Response"가 이름에 포함된 응답 스키마만 대상
            if "Response" not in _name:
                continue
            # datetime 필드가 있는지 확인
            has_datetime = any(
                field_info.annotation is datetime
                or (
                    hasattr(field_info.annotation, "__args__")
                    and datetime in (field_info.annotation.__args__ or ())
                )
                for field_info in cls.model_fields.values()
            )
            if has_datetime:
                result.append(cls)
    return result


def test_all_datetime_response_schemas_inherit_utc_base():
    """datetime 필드가 있는 모든 응답 스키마가 UTCDatetimeResponse를 상속하는지 확인한다."""
    schemas = _get_all_response_schemas()
    assert len(schemas) > 0, "datetime 필드가 있는 응답 스키마를 찾지 못했습니다"

    non_compliant = []
    for cls in schemas:
        if not issubclass(cls, UTCDatetimeResponse):
            non_compliant.append(cls.__name__)

    assert non_compliant == [], (
        f"UTCDatetimeResponse를 상속하지 않는 응답 스키마: {non_compliant}"
    )


def test_utc_datetime_response_serializes_with_z_suffix():
    """UTCDatetimeResponse 상속 스키마가 datetime을 Z 접미사로 직렬화하는지 확인한다."""
    # naive datetime (UTC로 간주)
    naive_dt = datetime(2024, 6, 15, 12, 30, 0)
    # aware datetime (KST)
    from datetime import timedelta
    kst = timezone(timedelta(hours=9))
    aware_dt = datetime(2024, 6, 15, 21, 30, 0, tzinfo=kst)

    # CeremonyPersonResponse로 직렬화 테스트 (이전에 누락되었던 스키마)
    from uuid import uuid4
    from app.schemas.ceremony_person import CeremonyPersonResponse

    response = CeremonyPersonResponse(
        id=uuid4(),
        user_id=uuid4(),
        name="테스트",
        relationship="친구",
        total_sent=100000,
        total_received=50000,
        event_count=3,
        created_at=naive_dt,
        updated_at=aware_dt,
    )

    data = response.model_dump()
    # datetime 필드가 Z 접미사 문자열로 직렬화되었는지 확인
    assert isinstance(data["created_at"], str)
    assert data["created_at"].endswith("Z"), f"Z 접미사 누락: {data['created_at']}"
    assert data["created_at"] == "2024-06-15T12:30:00Z"

    assert isinstance(data["updated_at"], str)
    assert data["updated_at"].endswith("Z"), f"Z 접미사 누락: {data['updated_at']}"
    # KST 21:30 → UTC 12:30
    assert data["updated_at"] == "2024-06-15T12:30:00Z"
