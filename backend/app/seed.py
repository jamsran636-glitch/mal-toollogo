"""Create the four required family accounts safely and idempotently."""

from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import User
from .security.hashing import hash_password


REQUIRED_USERS = (
    ("Шүрэнчулуун", "OWNER", "seed_owner_code", "99104047"),
    ("Адуучин", "HORSE_KEEPER", "seed_horse_code", "00000000"),
    ("Үхэрчин", "CATTLE_KEEPER", "seed_cattle_code", "00000000"),
    ("Хоньчин", "SHEEP_KEEPER", "seed_sheep_code", "00000000"),
)


def seed_users(*, allow_fixed_defaults: bool = False) -> int:
    settings = get_settings()

    configured_codes = {
        field_name: getattr(settings, field_name)
        for _, _, field_name, _ in REQUIRED_USERS
    }

    if not allow_fixed_defaults:
        missing = [
            field_name.upper()
            for field_name, value in configured_codes.items()
            if not value
        ]
        if missing:
            raise SystemExit(
                "Missing one-time seed environment values: " + ", ".join(missing)
            )

    created = 0

    with SessionLocal() as db:
        for username, role, code_field, fixed_code in REQUIRED_USERS:
            existing = db.scalar(
                select(User).where(User.username == username)
            )

            if existing is not None:
                continue

            code = configured_codes[code_field] or fixed_code

            db.add(
                User(
                    username=username,
                    role=role,
                    password_hash=hash_password(code),
                    is_active=True,
                    must_change_code=False,
                    token_version=1,
                )
            )
            created += 1

        db.commit()

    return created


if __name__ == "__main__":
    print(f"Seeded {seed_users()} account(s).")
