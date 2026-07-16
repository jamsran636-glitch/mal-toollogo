from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Мал тооллого API"
    app_env: str = "development"
    database_url: str = "sqlite:///./mal_tooollogo.db"
    cors_origins: str = "http://localhost:5173"
    jwt_secret: str = "development-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    login_window_minutes: int = 15
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    refresh_cookie_name: str = "mal_refresh"
    refresh_cookie_secure: bool = False
    upload_dir: str = "uploads"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "mal-images"
    storage_private: bool = True
    max_image_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 24_000_000
    max_backup_bytes: int = 50 * 1024 * 1024
    max_backup_expanded_bytes: int = 250 * 1024 * 1024
    backup_schema_version: int = 2
    seed_owner_code: str = ""
    seed_horse_code: str = ""
    seed_cattle_code: str = ""
    seed_sheep_code: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env.lower() == "test"

    @property
    def normalized_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_environment(self):
        if self.app_env.lower() not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production")
        if self.is_production:
            if self.normalized_database_url.startswith("sqlite"):
                raise ValueError("Production DATABASE_URL must use PostgreSQL")
            if (
                len(self.jwt_secret) < 32
                or self.jwt_secret == "development-only-secret-change-me"
            ):
                raise ValueError(
                    "Production JWT_SECRET must be a unique value of at least 32 characters"
                )
            if not self.cors_origin_list or self.cors_origin_list == ["*"]:
                raise ValueError(
                    "Production CORS_ORIGINS must contain explicit HTTPS origins"
                )
            if any(
                not origin.startswith("https://") for origin in self.cors_origin_list
            ):
                raise ValueError("Production CORS origins must use HTTPS")
            if not self.supabase_url or not self.supabase_service_role_key:
                raise ValueError(
                    "Production Supabase Storage configuration is required"
                )
            self.refresh_cookie_secure = True
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
