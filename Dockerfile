# MoneyLog 백엔드 FastAPI 애플리케이션 Docker 이미지
FROM python:3.12-slim

# 시스템 의존성 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 설치 (캐시 활용)
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# non-root 사용자 생성 (보안: 컨테이너 권한 상승 방지)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# 애플리케이션 코드 복사
COPY . .

# 파일 소유권을 non-root 사용자로 변경
RUN chown -R appuser:appgroup /app

# non-root 사용자로 전환
USER appuser

EXPOSE 8000

# uvicorn으로 앱 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
