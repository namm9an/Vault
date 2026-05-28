from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"
    APP_SECRET_KEY: str

    @field_validator("APP_SECRET_KEY")
    @classmethod
    def secret_key_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters")
        return v
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MINUTES: int = 60
    JWT_REFRESH_TTL_DAYS: int = 14
    CORS_ORIGINS: str = "http://localhost:5173"

    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"
    ARQ_REDIS_URL: str = "redis://redis:6379/1"

    TIR_BASE_URL: str = ""
    TIR_API_KEY: str = ""
    TIR_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"
    TIR_TIMEOUT_SECONDS: int = 60

    S3_ENDPOINT_URL: str = ""
    # Public-facing URL for presigned URLs returned to the browser.
    # For local dev with MinIO this is http://localhost:9000.
    # For E2E Object Storage this is the same as S3_ENDPOINT_URL.
    # When empty, presigned URLs use S3_ENDPOINT_URL as-is.
    S3_PUBLIC_URL: str = ""
    S3_REGION: str = "ap-south-1"
    S3_BUCKET: str = "vault-receipts"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PRESIGN_TTL_SECONDS: int = 300

    SMTP_HOST: str = "mailhog"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "digest@vault.local"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
