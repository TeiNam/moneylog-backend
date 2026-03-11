"""
환경 설정 로더 모듈 (Pydantic Settings 기반).

.env 파일 우선 로드 → .env 없고 AWS_SECRET_NAME 설정 시 Secrets Manager 폴백.
필수 항목(DATABASE_URL, JWT_SECRET_KEY) 누락 시 ValidationError 발생 → 앱 시작 중단.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# .env 파일 경로 (backend/ 디렉토리 기준)
_ENV_FILE_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """애플리케이션 환경 설정 모델."""

    # 데이터베이스
    DATABASE_URL: str  # PostgreSQL 비동기 연결 URL (필수)

    # JWT
    JWT_SECRET_KEY: str  # JWT 서명 시크릿 키 (필수)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AWS (운영 환경)
    AWS_REGION: str = "ap-northeast-2"
    AWS_SECRET_NAME: str | None = None  # Secrets Manager 시크릿 이름

    # 이메일 (SMTP)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None

    # Bedrock (AI 연동)
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    BEDROCK_REGION: str = "us-east-1"
    BEDROCK_TIMEOUT: int = 30

    # CORS 허용 오리진 (쉼표 구분, 운영 환경에서 도메인 목록 지정)
    ALLOWED_ORIGINS: str = "*"

    # 구독 배치 API 인증 키
    BATCH_API_KEY: str = ""

    # 앱
    APP_ENV: str = "development"  # development / staging / production
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE_PATH),
        env_file_encoding="utf-8",
    )

    @model_validator(mode="before")
    @classmethod
    def _load_from_secrets_manager(cls, values: dict) -> dict:
        """
        .env 파일이 없고 AWS_SECRET_NAME이 설정된 경우,
        AWS Secrets Manager에서 설정 값을 조회하여 채운다.
        """
        env_file_exists = _ENV_FILE_PATH.is_file()

        if env_file_exists:
            logger.info(".env 파일에서 환경 변수를 로드합니다: %s", _ENV_FILE_PATH)
            return values

        aws_secret_name = values.get("AWS_SECRET_NAME")
        if not aws_secret_name:
            logger.debug(
                ".env 파일이 없고 AWS_SECRET_NAME도 설정되지 않았습니다. "
                "환경 변수 또는 기본값을 사용합니다."
            )
            return values

        # boto3는 Secrets Manager 조회 시에만 lazy import (로컬 개발 시 불필요)
        logger.info(
            "AWS Secrets Manager에서 설정을 조회합니다: secret_name=%s",
            aws_secret_name,
        )
        try:
            import boto3  # noqa: PLC0415

            aws_region = values.get("AWS_REGION", "ap-northeast-2")
            client = boto3.client(
                "secretsmanager",
                region_name=aws_region,
            )
            response = client.get_secret_value(SecretId=aws_secret_name)
            secret_string = response.get("SecretString", "{}")
            secrets = json.loads(secret_string)

            # Secrets Manager 값으로 누락된 필드만 채움 (기존 값 우선)
            for key, value in secrets.items():
                upper_key = key.upper()
                if upper_key not in values or values[upper_key] is None:
                    values[upper_key] = value

            logger.info("AWS Secrets Manager에서 설정을 성공적으로 로드했습니다.")
        except ImportError:
            logger.error(
                "boto3 패키지가 설치되지 않았습니다. "
                "AWS Secrets Manager를 사용하려면 boto3를 설치하세요."
            )
            raise
        except Exception:
            logger.exception(
                "AWS Secrets Manager에서 설정 조회 중 오류가 발생했습니다: "
                "secret_name=%s",
                aws_secret_name,
            )
            raise

        return values


@lru_cache
def get_settings() -> Settings:
    """Settings 싱글턴 인스턴스를 반환한다 (lru_cache로 캐싱)."""
    return Settings()  # type: ignore[call-arg]
