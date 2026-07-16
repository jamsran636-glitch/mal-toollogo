import os

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "pytest-only-secret-that-is-at-least-32-characters")
os.environ.setdefault(
    "UPLOAD_DIR", os.path.join(os.environ.get("TEMP", "."), "mal-pytest-uploads")
)
os.environ["LOGIN_MAX_FAILURES"] = "5"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.security.hashing import hash_password


TEST_ACCOUNTS = (
    ("Шүрэнчулуун", "99104047", "OWNER"),
    ("Адуучин", "00000000", "HORSE_KEEPER"),
    ("Үхэрчин", "00000000", "CATTLE_KEEPER"),
    ("Хоньчин", "00000000", "SHEEP_KEEPER"),
)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for username, code, role in TEST_ACCOUNTS:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(code),
                    role=role,
                    must_change_code=False,
                )
            )
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


def login(client: TestClient, username: str, code: str) -> tuple[str, dict]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "code": code}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["access_token"], payload["user"]


def headers(token: str, *, idempotency_key: str | None = None) -> dict[str, str]:
    result = {"Authorization": f"Bearer {token}"}
    if idempotency_key:
        result["Idempotency-Key"] = idempotency_key
    return result


@pytest.fixture
def owner(client):
    return login(client, "Шүрэнчулуун", "99104047")[0]


@pytest.fixture
def horse_worker(client):
    return login(client, "Адуучин", "00000000")[0]


@pytest.fixture
def cattle_worker(client):
    return login(client, "Үхэрчин", "00000000")[0]


@pytest.fixture
def sheep_worker(client):
    return login(client, "Хоньчин", "00000000")[0]
