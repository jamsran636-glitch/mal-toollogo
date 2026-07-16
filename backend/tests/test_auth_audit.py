from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import AuditLog, HorseGroup, User, UserSession
from app.security.hashing import verify_password
from tests.conftest import TEST_ACCOUNTS, headers, login


def test_seeded_accounts_are_hashed_and_login(client):
    with SessionLocal() as db:
        users = list(db.scalars(select(User).order_by(User.username)).all())
        assert len(users) == 4
        for user in users:
            assert user.password_hash.startswith("$argon2id$")
            assert all(code not in user.password_hash for _, code, _ in TEST_ACCOUNTS)
    for username, code, role in TEST_ACCOUNTS:
        token, info = login(client, username, code)
        assert token and info["role"] == role


def test_invalid_login_throttles_and_audits(client):
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/login", json={"username": "Адуучин", "code": "wrong-code"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "Адуучин", "code": "wrong-code"}
        ).status_code
        == 429
    )
    with SessionLocal() as db:
        actions = list(db.scalars(select(AuditLog.action)).all())
        assert actions.count("LOGIN_FAILED") == 5
        assert "LOGIN_BLOCKED" in actions


def test_disabled_user_and_logout_revocation(client):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "Адуучин"))
        user.is_active = False
        db.commit()
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "Адуучин", "code": "00000000"}
        ).status_code
        == 401
    )

    token, _ = login(client, "Шүрэнчулуун", "99104047")
    assert client.get("/api/v1/auth/me", headers=headers(token)).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers(token)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers(token)).status_code == 401


def test_expired_token_rejected(client, owner):
    settings = get_settings()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "Шүрэнчулуун"))
        session = db.scalar(select(UserSession).where(UserSession.user_id == user.id))
        now = datetime.now(timezone.utc)
        expired = jwt.encode(
            {
                "sub": user.id,
                "sid": session.id,
                "ver": user.token_version,
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
                "type": "access",
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
    assert client.get("/api/v1/auth/me", headers=headers(expired)).status_code == 401


def test_role_is_reread_from_database(client, horse_worker):
    assert (
        client.get("/api/v1/horses/access", headers=headers(horse_worker)).status_code
        == 200
    )
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "Адуучин"))
        user.role = "CATTLE_KEEPER"
        db.commit()
    assert (
        client.get("/api/v1/horses/access", headers=headers(horse_worker)).status_code
        == 403
    )
    assert (
        client.get("/api/v1/cattle/access", headers=headers(horse_worker)).status_code
        == 200
    )


def test_authorization_matrix(client):
    tokens = {
        name: login(client, username, code)[0]
        for name, (username, code) in {
            "owner": ("Шүрэнчулуун", "99104047"),
            "horse": ("Адуучин", "00000000"),
            "cattle": ("Үхэрчин", "00000000"),
            "sheep": ("Хоньчин", "00000000"),
        }.items()
    }
    paths = [
        "/api/v1/horses/access",
        "/api/v1/cattle/access",
        "/api/v1/small-livestock/access",
        "/api/v1/analytics/access",
    ]
    expected = {
        "owner": [200, 200, 200, 200],
        "horse": [200, 403, 403, 403],
        "cattle": [403, 200, 403, 403],
        "sheep": [403, 403, 200, 403],
    }
    for role, token in tokens.items():
        assert [
            client.get(path, headers=headers(token)).status_code for path in paths
        ] == expected[role]
    for owner_path in (
        "/api/v1/audit",
        "/api/v1/herders",
        "/api/v1/finance",
        "/api/v1/backup",
    ):
        assert (
            client.get(owner_path, headers=headers(tokens["horse"])).status_code == 403
        )


def test_client_cannot_create_audit(client, horse_worker):
    assert (
        client.post(
            "/api/v1/audit", headers=headers(horse_worker), json={"action": "FORGED"}
        ).status_code
        == 405
    )


def test_mutation_and_audit_are_atomic(client, horse_worker, monkeypatch):
    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr("app.api.horses.write_audit", fail_audit)
    try:
        client.post(
            "/api/v1/horses/groups",
            headers=headers(horse_worker),
            json={"name": "Rollback group"},
        )
    except RuntimeError:
        pass
    with SessionLocal() as db:
        assert (
            db.scalar(select(HorseGroup).where(HorseGroup.name == "Rollback group"))
            is None
        )


def test_change_code_revokes_sessions(client, owner):
    response = client.post(
        "/api/v1/auth/change-code",
        headers=headers(owner),
        json={"current_code": "99104047", "new_code": "new-secure-code-123"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers(owner)).status_code == 401
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "Шүрэнчулуун"))
        assert verify_password("new-secure-code-123", user.password_hash)
