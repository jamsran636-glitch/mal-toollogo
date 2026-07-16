"""Seed the four required accounts without storing plaintext codes in source.

Set all four SEED_*_CODE environment variables, run ``python -m app.seed``,
then remove those variables from the deployment environment.
"""

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import User
from .security.hashing import hash_password


REQUIRED_USERS = (
    ("Шүрэнчулуун", "OWNER", "seed_owner_code"),
    ("Адуучин", "HORSE_KEEPER", "seed_horse_code"),
    ("Үхэрчин", "CATTLE_KEEPER", "seed_cattle_code"),
    ("Хоньчин", "SHEEP_KEEPER", "seed_sheep_code"),
)


def seed_users() -> int:
    settings = get_settings()
    codes = {field: getattr(settings, field) for _, _, field in REQUIRED_USERS}
    missing = [field.upper() for field, value in codes.items() if not value]
    if missing:
        raise SystemExit(
            "Missing one-time seed environment values: " + ", ".join(missing)
        )

    created = 0
    with SessionLocal() as db:
        for username, role, code_field in REQUIRED_USERS:
            if db.scalar(select(User).where(User.username == username)) is not None:
                continue
            db.add(
                User(
                    username=username,
                    role=role,
                    password_hash=hash_password(codes[code_field]),
                    must_change_code=True,
                )
            )
            created += 1
        db.commit()
    return created


if __name__ == "__main__":
    print(f"Seeded {seed_users()} account(s).")
