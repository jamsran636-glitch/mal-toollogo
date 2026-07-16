"""Isolated local server used only by Playwright."""

import os
from pathlib import Path


database = Path(__file__).resolve().parent / "e2e.db"
database.unlink(missing_ok=True)
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
os.environ["JWT_SECRET"] = "playwright-only-secret-that-is-at-least-32-characters"
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:4173"
os.environ["UPLOAD_DIR"] = str(Path(__file__).resolve().parent / "e2e_uploads")

import uvicorn

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.security.hashing import hash_password


accounts = (
    ("Шүрэнчулуун", "99104047", "OWNER"),
    ("Адуучин", "00000000", "HORSE_KEEPER"),
    ("Үхэрчин", "00000000", "CATTLE_KEEPER"),
    ("Хоньчин", "00000000", "SHEEP_KEEPER"),
)


def prepare() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for username, code, role in accounts:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(code),
                    role=role,
                    must_change_code=False,
                )
            )
        db.commit()


if __name__ == "__main__":
    prepare()
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
