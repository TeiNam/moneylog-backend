---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/*.pyi"
---
# Python Rules

> `.py` / `.pyi` 파일이 열릴 때 자동으로 로드됩니다.

## Coding Style
- 공개 API에 타입 힌트 필수 (Python 3.10+ `X | None`)
- Comprehension 한 단계 중첩까지, 복잡하면 일반 루프
- `with`문으로 리소스 관리, async에서 sync blocking 금지
- `@dataclass(frozen=True)` 불변 값 객체
- black + isort + ruff, f-string 사용

## Patterns
- 도메인별 패키지 구조, `Protocol`로 인터페이스
- 내부: dataclass, 외부 입력: Pydantic
- FastAPI `Depends()`, 도메인별 커스텀 예외, bare except 금지
- `pydantic_settings.BaseSettings`로 환경 변수 관리

## Testing
- pytest 기본, fixture(function scope), parametrize
- pytest-asyncio, pytest.raises, conftest.py
- `pytest --cov=app --cov-report=term-missing`

## Security
- SQL 파라미터화 쿼리, Pydantic 입력 검증
- 시크릿: `os.environ[]`, pickle/eval 금지
- bcrypt + `hmac.compare_digest`, shell=True 금지
- 로깅에 시크릿 절대 포함 금지
