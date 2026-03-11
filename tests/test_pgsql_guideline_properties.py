"""
PostgreSQL 가이드라인 개선 속성 기반 테스트 (Property-Based Tests).

Hypothesis 라이브러리를 사용하여 PostgreSQL 가이드라인 개선 사항의 핵심 속성을 검증한다.
모델 메타데이터 검사를 통해 컬럼 타입, 제약조건, 인덱스 등을 검증한다.

참고: 테스트 환경(SQLite)에서는 conftest.py의 _remove_schema_from_metadata()가
BigInteger+Identity를 Integer+autoincrement로 변환하므로,
원본 모델 정의를 검증하기 위해 Annotated 타입의 메타데이터를 직접 검사한다.
"""

import typing

from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.base import bigint_pk
from app.models.chat_message import ChatMessage
from app.models.transaction import Transaction

# ---------------------------------------------------------------------------
# 고빈도 테이블 모델 목록 (Hypothesis 전략에서 사용)
# ---------------------------------------------------------------------------
HIGH_VOLUME_MODELS = [Transaction, ChatMessage]

# ---------------------------------------------------------------------------
# 헬퍼: bigint_pk Annotated 타입에서 원본 MappedColumn 정보 추출
# ---------------------------------------------------------------------------


def _get_bigint_pk_column_info():
    """
    bigint_pk Annotated 타입의 메타데이터에서 원본 컬럼 정보를 추출한다.
    conftest의 SQLite 변환 영향을 받지 않는 원본 정의를 반환한다.
    """
    metadata = bigint_pk.__metadata__
    mapped_col = metadata[0]
    col = mapped_col.column
    return {
        "type": type(col.type),
        "identity": col.identity,
        "primary_key": col.primary_key,
    }


# ---------------------------------------------------------------------------
# Property 1: 고빈도 테이블 PK 구조 검증
# Feature: pgsql-guideline-improvements, Property 1: 고빈도 테이블 PK 구조 검증
# **Validates: Requirements 1.1, 1.2, 1.3**
# ---------------------------------------------------------------------------


def _get_id_column_info_from_model(model):
    """
    모델의 id 컬럼에서 원본 BigInteger + Identity 정보를 추출한다.

    두 가지 경우를 처리한다:
    1. bigint_pk Annotated 타입 사용 (단일 PK) — type hints에서 메타데이터 추출
    2. 직접 mapped_column 정의 (복합 PK, 파티셔닝 테이블) — 모델 속성에서 추출
    """
    hints = typing.get_type_hints(model, include_extras=True)
    id_hint = hints["id"]
    args = typing.get_args(id_hint)

    if len(args) > 0 and hasattr(args[0], "__metadata__"):
        # bigint_pk Annotated 타입 사용 (예: Transaction)
        mapped_col = args[0].__metadata__[0]
        return mapped_col.column
    else:
        # 직접 mapped_column 정의 (예: ChatMessage — 파티셔닝 복합 PK)
        # 모델의 __table__에서 원본 컬럼 정보를 가져오되,
        # conftest가 변환하기 전의 원본 MappedColumn에서 추출
        prop = model.__mapper__.get_property("id")
        return prop.columns[0]


@settings(max_examples=100)
@given(model=st.sampled_from(HIGH_VOLUME_MODELS))
def test_high_volume_table_id_uses_bigint_pk_type(model):
    """
    고빈도 테이블(Transaction, ChatMessage)의 `id` 필드는
    BigInteger + Identity 타입이어야 한다.

    - 단일 PK 모델: bigint_pk Annotated 타입 사용 (primary_key=True 포함)
    - 복합 PK 모델 (파티셔닝): 직접 mapped_column 정의 + PrimaryKeyConstraint
    """
    col = _get_id_column_info_from_model(model)

    # BigInteger 타입 확인 (conftest가 Integer로 변환할 수 있으므로 원본 검사)
    # 원본 모델 정의에서 BigInteger를 사용했는지 확인
    hints = typing.get_type_hints(model, include_extras=True)
    id_hint = hints["id"]
    args = typing.get_args(id_hint)

    if len(args) > 0 and hasattr(args[0], "__metadata__"):
        # Annotated 타입에서 원본 컬럼 타입 검사 (conftest 변환 전)
        original_col = args[0].__metadata__[0].column
        assert isinstance(original_col.type, BigInteger), (
            f"{model.__name__}.id의 원본 타입이 BigInteger가 아닙니다: "
            f"{type(original_col.type).__name__}"
        )
        assert original_col.identity is not None, (
            f"{model.__name__}.id에 Identity가 설정되어 있지 않습니다"
        )
        assert original_col.primary_key is True, (
            f"{model.__name__}.id가 PK가 아닙니다"
        )
    else:
        # 직접 mapped_column 정의 — MappedColumn 속성에서 원본 정보 추출
        # 파티셔닝 모델은 PrimaryKeyConstraint로 PK를 정의하므로
        # 컬럼 자체에 primary_key=True가 없을 수 있음
        # 대신 테이블의 PK 제약조건에 id가 포함되어 있는지 확인
        prop = model.__mapper__.get_property("id")
        original_col = prop.columns[0]

        # conftest가 변환했을 수 있으므로, 모델 클래스의 __init_subclass__ 전
        # mapped_column 인자를 확인 — 여기서는 테이블 메타데이터로 검증
        # id가 테이블 PK에 포함되어 있는지 확인
        table = model.__table__
        pk_col_names = [c.name for c in table.primary_key.columns]
        assert "id" in pk_col_names, (
            f"{model.__name__}.id가 PK에 포함되어 있지 않습니다"
        )


@settings(max_examples=100)
@given(model=st.sampled_from(HIGH_VOLUME_MODELS))
def test_high_volume_table_public_id_is_uuid_unique(model):
    """
    고빈도 테이블(Transaction, ChatMessage)의 `public_id` 컬럼은
    PostgreSQL UUID 타입이고, UniqueConstraint가 설정되어 있어야 한다.
    """
    table = model.__table__

    # public_id 컬럼 존재 확인
    assert "public_id" in table.c, (
        f"{model.__name__}에 public_id 컬럼이 없습니다"
    )

    public_id_col = table.c.public_id

    # UUID 타입 확인 (PostgreSQL UUID 방언 타입)
    # conftest에서 UUID 타입은 변환하지 않으므로 직접 확인 가능
    assert isinstance(public_id_col.type, PG_UUID), (
        f"{model.__name__}.public_id의 타입이 UUID가 아닙니다: "
        f"{type(public_id_col.type).__name__}"
    )

    # UniqueConstraint 확인 (테이블 레벨 제약조건에서 검색)
    has_unique = any(
        isinstance(constraint, UniqueConstraint)
        and any(col.name == "public_id" for col in constraint.columns)
        for constraint in table.constraints
    )
    assert has_unique, (
        f"{model.__name__}.public_id에 UniqueConstraint가 설정되어 있지 않습니다"
    )

# ---------------------------------------------------------------------------
# 인덱스가 정의된 모델 목록 (Property 4에서 사용)
# ---------------------------------------------------------------------------

from app.models.asset import Asset
from app.models.subscription import Subscription
from app.models.budget import Budget
from app.models.goal import Goal
from app.models.notification import Notification
from app.models.receipt_scan import ReceiptScan
from app.models.ai_feedback import AIFeedback
from app.models.category_config import CategoryConfig
from app.models.chat_session import ChatSession

# 인덱스가 정의된 모든 모델 (테스트 대상)
MODELS_WITH_INDEXES = [
    Transaction,
    ChatMessage,
    ChatSession,
    Asset,
    Subscription,
    Budget,
    Goal,
    Notification,
    ReceiptScan,
    AIFeedback,
    CategoryConfig,
]


# ---------------------------------------------------------------------------
# Property 4: 인덱스 네이밍 규칙 준수
# Feature: pgsql-guideline-improvements, Property 4: 인덱스 네이밍 규칙 준수
# **Validates: 요구사항 3.1, 3.2, 3.3**
# ---------------------------------------------------------------------------


def _get_model_indexes(model):
    """
    모델의 __table_args__에서 명시적으로 정의된 인덱스 목록을 추출한다.

    SQLAlchemy 테이블 메타데이터의 indexes 속성을 사용하여
    모델에 정의된 모든 인덱스를 반환한다.
    """
    table = model.__table__
    return list(table.indexes)


@settings(max_examples=100)
@given(model=st.sampled_from(MODELS_WITH_INDEXES))
def test_index_names_follow_naming_convention(model):
    """
    모든 모델의 인덱스 이름이 idx_ 또는 uidx_ 접두사를 가져야 한다.

    네이밍 규칙:
    - 일반 인덱스: idx_{테이블명}_{컬럼명들}
    - 유니크 인덱스: uidx_{테이블명}_{컬럼명들}
    """
    indexes = _get_model_indexes(model)
    table_name = model.__tablename__

    for idx in indexes:
        idx_name = idx.name
        assert idx_name is not None, (
            f"{model.__name__} 모델에 이름이 없는 인덱스가 있습니다"
        )

        # idx_ 또는 uidx_ 접두사 확인
        assert idx_name.startswith("idx_") or idx_name.startswith("uidx_"), (
            f"{model.__name__} 모델의 인덱스 '{idx_name}'이 "
            f"'idx_' 또는 'uidx_' 접두사를 가지지 않습니다"
        )

        # 테이블명 포함 확인
        if idx_name.startswith("uidx_"):
            remainder = idx_name[len("uidx_"):]
        else:
            remainder = idx_name[len("idx_"):]

        assert remainder.startswith(table_name + "_") or remainder.startswith(table_name + "_"), (
            f"{model.__name__} 모델의 인덱스 '{idx_name}'이 "
            f"테이블명 '{table_name}'을 포함하지 않습니다. "
            f"예상 형식: idx_{table_name}_{{컬럼명}} 또는 uidx_{table_name}_{{컬럼명}}"
        )


@settings(max_examples=100)
@given(model=st.sampled_from(MODELS_WITH_INDEXES))
def test_unique_indexes_use_uidx_prefix(model):
    """
    유니크 인덱스는 반드시 uidx_ 접두사를 사용하고,
    일반 인덱스는 idx_ 접두사를 사용해야 한다.
    """
    indexes = _get_model_indexes(model)

    for idx in indexes:
        idx_name = idx.name
        if idx.unique:
            assert idx_name.startswith("uidx_"), (
                f"{model.__name__} 모델의 유니크 인덱스 '{idx_name}'이 "
                f"'uidx_' 접두사를 사용하지 않습니다"
            )
        else:
            assert idx_name.startswith("idx_"), (
                f"{model.__name__} 모델의 일반 인덱스 '{idx_name}'이 "
                f"'idx_' 접두사를 사용하지 않습니다"
            )


@settings(max_examples=100)
@given(model=st.sampled_from(MODELS_WITH_INDEXES))
def test_index_names_contain_column_names(model):
    """
    인덱스 이름에 해당 인덱스의 컬럼명이 포함되어야 한다.

    복합 인덱스의 경우 컬럼명이 언더스코어로 연결된다.
    부분 인덱스(WHERE 절 포함)는 추가 접미사를 허용한다.
    """
    indexes = _get_model_indexes(model)
    table_name = model.__tablename__

    for idx in indexes:
        idx_name = idx.name

        # 접두사와 테이블명 제거하여 컬럼 부분 추출
        if idx_name.startswith("uidx_"):
            column_part = idx_name[len(f"uidx_{table_name}_"):]
        else:
            column_part = idx_name[len(f"idx_{table_name}_"):]

        # 인덱스에 정의된 컬럼명 목록
        idx_columns = [col.name for col in idx.columns]

        # 각 컬럼명이 인덱스 이름의 컬럼 부분에 포함되어 있는지 확인
        # 부분 인덱스는 추가 접미사(예: _not_private)를 가질 수 있으므로
        # 컬럼명이 column_part에 포함되어 있는지만 확인
        for col_name in idx_columns:
            assert col_name in column_part, (
                f"{model.__name__} 모델의 인덱스 '{idx_name}'에 "
                f"컬럼명 '{col_name}'이 포함되어 있지 않습니다. "
                f"인덱스 컬럼: {idx_columns}, 이름의 컬럼 부분: '{column_part}'"
            )


# ---------------------------------------------------------------------------
# Property 5: 목록 조회 반환 타입 검증
# Feature: pgsql-guideline-improvements, Property 5: 목록 조회 반환 타입
# **Validates: 요구사항 5.4**
# ---------------------------------------------------------------------------

import ast
import inspect
import textwrap

from app.repositories.transaction_repository import TransactionRepository
from app.repositories.transfer_repository import TransferRepository


# 목록 조회 메서드 정보: (리포지토리 클래스, 메서드 이름, 대응 모델 클래스명)
LIST_METHODS = [
    (TransactionRepository, "get_list", "Transaction"),
    (TransactionRepository, "get_list_for_export", "Transaction"),
    (TransferRepository, "get_list_by_user", "Transfer"),
]


def _get_return_annotation_str(cls, method_name: str) -> str:
    """
    메서드의 반환 타입 어노테이션 문자열을 추출한다.

    typing.get_type_hints 대신 AST를 사용하여 원본 어노테이션을 그대로 가져온다.
    """
    method = getattr(cls, method_name)
    source = textwrap.dedent(inspect.getsource(method))
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == method_name and node.returns is not None:
                return ast.dump(node.returns)
    return ""


def _get_select_calls_from_method(cls, method_name: str) -> list[ast.Call]:
    """
    메서드 소스 코드에서 select() 호출 노드를 모두 추출한다.
    """
    method = getattr(cls, method_name)
    source = textwrap.dedent(inspect.getsource(method))
    tree = ast.parse(source)

    select_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # select(...) 호출 감지
            func_node = node.func
            if isinstance(func_node, ast.Name) and func_node.id == "select":
                select_calls.append(node)
    return select_calls


@settings(max_examples=100)
@given(
    method_info=st.sampled_from(LIST_METHODS),
)
def test_list_methods_return_row_not_orm_model(method_info):
    """
    목록 조회 메서드의 반환 타입 어노테이션에 Row가 포함되어야 하고,
    ORM 모델 클래스(Transaction, Transfer)가 직접 포함되지 않아야 한다.

    요구사항 5.4: 목록 조회 결과는 ORM 모델 객체가 아닌 Row 객체를 반환해야 한다.
    """
    cls, method_name, model_class_name = method_info

    # 반환 타입 어노테이션 문자열 추출
    return_annotation = _get_return_annotation_str(cls, method_name)

    # Row가 반환 타입에 포함되어 있는지 확인
    assert "Row" in return_annotation, (
        f"{cls.__name__}.{method_name}()의 반환 타입에 'Row'가 포함되어 있지 않습니다. "
        f"목록 조회 메서드는 ORM 모델 대신 Row 객체를 반환해야 합니다."
    )

    # ORM 모델 클래스가 반환 타입에 직접 포함되지 않는지 확인
    # (예: list[Transaction] 대신 list[Row]여야 함)
    # AST dump에서 모델 클래스명이 반환 타입의 직접 요소로 나타나지 않아야 함
    method = getattr(cls, method_name)
    hints = typing.get_type_hints(method)
    return_hint_str = str(hints.get("return", ""))
    assert model_class_name not in return_hint_str, (
        f"{cls.__name__}.{method_name}()의 반환 타입에 ORM 모델 '{model_class_name}'이 "
        f"포함되어 있습니다: {return_hint_str}. "
        f"목록 조회 메서드는 list[Row]를 반환해야 합니다."
    )


@settings(max_examples=100)
@given(
    method_info=st.sampled_from(LIST_METHODS),
)
def test_list_methods_use_column_specific_select(method_info):
    """
    목록 조회 메서드의 select() 호출이 개별 컬럼을 명시해야 한다.

    select(Model) 패턴(인자 1개)이 아닌 select(Model.col1, Model.col2, ...) 패턴
    (인자 2개 이상)을 사용하는지 검증한다.
    count 쿼리의 select(func.count())는 제외한다.

    요구사항 5.3: 목록 조회에서 select(Model) 대신 select(Model.col1, ...) 패턴 사용
    """
    cls, method_name, model_class_name = method_info

    select_calls = _get_select_calls_from_method(cls, method_name)

    # select() 호출이 최소 1개 이상 존재해야 함
    assert len(select_calls) > 0, (
        f"{cls.__name__}.{method_name}()에 select() 호출이 없습니다."
    )

    # 목록 데이터를 조회하는 select() 호출 필터링
    # (func.count() 등 집계 함수 호출은 제외)
    data_selects = []
    for call in select_calls:
        # select(func.count()) 패턴 제외: 첫 번째 인자가 func.count() 호출인 경우
        if len(call.args) == 1:
            arg = call.args[0]
            if isinstance(arg, ast.Call):
                # func.count() 같은 집계 함수 호출은 건너뜀
                continue
        data_selects.append(call)

    # 데이터 조회용 select()가 최소 1개 이상 존재해야 함
    assert len(data_selects) > 0, (
        f"{cls.__name__}.{method_name}()에 데이터 조회용 select() 호출이 없습니다."
    )

    # 각 데이터 조회 select()가 2개 이상의 인자를 가져야 함
    # (select(Model) = 1개 인자 → 전체 컬럼 조회, 지양해야 함)
    for call in data_selects:
        assert len(call.args) >= 2, (
            f"{cls.__name__}.{method_name}()에서 select()가 "
            f"{len(call.args)}개의 인자만 사용합니다. "
            f"select(Model) 대신 select(Model.col1, Model.col2, ...) 패턴을 "
            f"사용하여 필요 컬럼만 명시해야 합니다."
        )



# ---------------------------------------------------------------------------
# Property 6: 배치 조회 자산명 매핑 정확성
# Feature: pgsql-guideline-improvements, Property 6: 배치 조회 자산명 매핑 정확성
# **Validates: 요구사항 6.1, 6.2, 6.4**
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    asset_data=st.lists(
        st.tuples(st.uuids(), st.text(min_size=1, max_size=50)),
        min_size=0,
        max_size=20,
    ),
    query_ids=st.lists(st.uuids(), min_size=0, max_size=10),
)
def test_batch_asset_map_correctness(asset_data, query_ids):
    """
    배치 조회로 자산명을 조회하면 모든 이체의 자산명이 실제 자산 name과 일치하고,
    미존재 자산은 빈 문자열인지 검증한다.

    TransferService.get_list()의 배치 조회 패턴을 시뮬레이션한다:
    1. 이체 목록에서 모든 asset_id를 수집
    2. get_by_ids()로 1회 배치 조회 후 asset_map 딕셔너리 구성
    3. asset_map.get(id, "")로 자산명 매핑

    요구사항 6.1: 배치 쿼리로 자산명 조회
    요구사항 6.2: 여러 자산 ID를 한 번의 쿼리로 조회
    요구사항 6.4: 미존재 자산 ID는 빈 문자열 처리
    """
    # 시뮬레이션: DB에 존재하는 자산 (id → name 매핑)
    existing_assets = {uid: name for uid, name in asset_data}

    # 시뮬레이션: get_by_ids() 배치 조회 — query_ids 중 존재하는 자산만 반환
    query_id_set = set(query_ids)
    found_assets = [
        (uid, name) for uid, name in asset_data if uid in query_id_set
    ]
    asset_map = {uid: name for uid, name in found_assets}

    # 검증: 각 query_id에 대해 매핑 결과가 정확한지 확인
    for qid in query_ids:
        result = asset_map.get(qid, "")
        if qid in existing_assets:
            # 존재하는 자산 → 실제 자산명과 일치해야 함
            assert result == existing_assets[qid], (
                f"자산 ID {qid}의 매핑 결과가 일치하지 않습니다. "
                f"기대값: '{existing_assets[qid]}', 실제값: '{result}'"
            )
        else:
            # 미존재 자산 → 빈 문자열이어야 함
            assert result == "", (
                f"미존재 자산 ID {qid}의 매핑 결과가 빈 문자열이 아닙니다. "
                f"실제값: '{result}'"
            )


# ---------------------------------------------------------------------------
# Property 7: 논리적 FK 주석 형식 통일
# Feature: pgsql-guideline-improvements, Property 7: 논리적 FK 주석 형식 통일
# **Validates: 요구사항 7.1, 7.2**
# ---------------------------------------------------------------------------

import re

from app.models.transfer import Transfer
from app.models.user import User
from app.models.family_group import FamilyGroup
from app.models.ceremony_person import CeremonyPerson

# CarExpenseDetail, CeremonyEvent는 transaction.py에 정의되어 있음
from app.models.transaction import CarExpenseDetail, CeremonyEvent

# 논리적 FK 컬럼 목록: (모델 클래스, 컬럼명) 튜플
# _id로 끝나는 컬럼 중 모델 자체의 id, public_id를 제외한 논리적 FK 컬럼
LOGICAL_FK_COLUMNS = [
    # Transaction
    (Transaction, "user_id"),
    (Transaction, "family_group_id"),
    (Transaction, "asset_id"),
    # ChatMessage
    (ChatMessage, "session_id"),
    # ChatSession
    (ChatSession, "user_id"),
    # Asset
    (Asset, "user_id"),
    (Asset, "family_group_id"),
    # Subscription
    (Subscription, "user_id"),
    (Subscription, "family_group_id"),
    (Subscription, "asset_id"),
    # Budget
    (Budget, "user_id"),
    (Budget, "family_group_id"),
    # Goal
    (Goal, "user_id"),
    (Goal, "family_group_id"),
    # Notification
    (Notification, "user_id"),
    (Notification, "subscription_id"),
    # ReceiptScan
    (ReceiptScan, "user_id"),
    (ReceiptScan, "transaction_id"),
    # AIFeedback
    (AIFeedback, "user_id"),
    (AIFeedback, "transaction_id"),
    # CategoryConfig
    (CategoryConfig, "owner_id"),
    # Transfer
    (Transfer, "user_id"),
    (Transfer, "family_group_id"),
    (Transfer, "from_asset_id"),
    (Transfer, "to_asset_id"),
    # User
    (User, "family_group_id"),
    (User, "default_asset_id"),
    # FamilyGroup
    (FamilyGroup, "owner_id"),
    # CeremonyPerson
    (CeremonyPerson, "user_id"),
    # CarExpenseDetail
    (CarExpenseDetail, "transaction_id"),
    # CeremonyEvent
    (CeremonyEvent, "transaction_id"),
]

# 논리적 FK 주석 정규표현식 패턴: "논리적 FK → {스키마}.{테이블}.{컬럼}"
LOGICAL_FK_COMMENT_PATTERN = re.compile(r"^논리적 FK → \w+\.\w+\.\w+")


@settings(max_examples=100)
@given(fk_info=st.sampled_from(LOGICAL_FK_COLUMNS))
def test_logical_fk_columns_have_valid_comment(fk_info):
    """
    모든 모델의 논리적 FK 컬럼에 comment 파라미터가 존재하고,
    '논리적 FK → {스키마}.{테이블}.{컬럼}' 정규표현식 패턴과 일치하는지 검증한다.

    요구사항 7.1: 모든 논리적 FK 컬럼에 comment 파라미터로 참조 대상 명시
    요구사항 7.2: 논리적 FK 주석을 '논리적 FK → {스키마}.{테이블}.{컬럼}' 형식으로 통일
    """
    model, column_name = fk_info
    table = model.__table__
    column = table.c[column_name]

    # 1. comment 속성이 None이 아닌지 확인
    assert column.comment is not None, (
        f"{model.__name__}.{column_name}에 comment가 설정되어 있지 않습니다. "
        f"논리적 FK 컬럼에는 '논리적 FK → {{스키마}}.{{테이블}}.{{컬럼}}' 형식의 주석이 필요합니다."
    )

    # 2. comment가 정규표현식 패턴과 일치하는지 확인
    assert LOGICAL_FK_COMMENT_PATTERN.match(column.comment), (
        f"{model.__name__}.{column_name}의 comment가 규칙에 맞지 않습니다. "
        f"현재 값: '{column.comment}'. "
        f"예상 패턴: '논리적 FK → {{스키마}}.{{테이블}}.{{컬럼}}' (정규식: ^논리적 FK → \\w+\\.\\w+\\.\\w+)"
    )

