import pytest
from pydantic import ValidationError

from app.config import Settings


def test_plain_postgres_urls_normalize_to_psycopg():
    settings = Settings(app_env="test", database_url="postgresql://user:pass@db.example/test")
    assert settings.normalized_database_url.startswith("postgresql+psycopg://")


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "sqlite:///unsafe.db"},
        {"jwt_secret": "short"},
        {"cors_origins": "*"},
        {"cors_origins": "http://example.com"},
        {"supabase_service_role_key": ""},
    ],
)
def test_production_rejects_unsafe_configuration(overrides):
    values = {
        "app_env": "production",
        "database_url": "postgresql://user:pass@db.example/app?sslmode=require",
        "jwt_secret": "unique-production-test-secret-at-least-32-characters",
        "cors_origins": "https://app.example.com",
        "supabase_url": "https://project.supabase.co",
        "supabase_service_role_key": "test-only-not-a-real-key",
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        Settings(**values)
