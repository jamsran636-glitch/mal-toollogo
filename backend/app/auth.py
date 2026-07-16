from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import LoginAttempt, User, UserSession
from .security.hashing import hash_token, new_refresh_token


settings = get_settings()
bearer = HTTPBearer(auto_error=False)

ROLE_OWNER = "OWNER"
ROLE_HORSE = "HORSE_KEEPER"
ROLE_CATTLE = "CATTLE_KEEPER"
ROLE_SHEEP = "SHEEP_KEEPER"

MODULE_HORSES = "horses"
MODULE_CATTLE = "cattle"
MODULE_SMALL = "small_livestock"
MODULE_ANALYTICS = "analytics"
MODULE_FINANCE = "finance"
MODULE_HERDERS = "herders"
MODULE_AUDIT = "audit"
MODULE_REPORTS = "reports"
MODULE_BACKUP = "backup"
MODULE_MORTALITY = "mortality"

ROLE_MODULES: dict[str, tuple[str, ...]] = {
    ROLE_OWNER: (
        MODULE_HORSES,
        MODULE_CATTLE,
        MODULE_SMALL,
        MODULE_ANALYTICS,
        MODULE_FINANCE,
        MODULE_HERDERS,
        MODULE_AUDIT,
        MODULE_REPORTS,
        MODULE_BACKUP,
        MODULE_MORTALITY,
    ),
    ROLE_HORSE: (MODULE_HORSES,),
    ROLE_CATTLE: (MODULE_CATTLE,),
    ROLE_SHEEP: (MODULE_SMALL,),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str
    role: str
    allowed_modules: tuple[str, ...]
    session_id: str
    token_version: int
    must_change_code: bool


def auth_user(user: User, session_id: str) -> AuthUser:
    return AuthUser(
        id=user.id,
        username=user.username,
        role=user.role,
        allowed_modules=ROLE_MODULES.get(user.role, ()),
        session_id=session_id,
        token_version=user.token_version,
        must_change_code=user.must_change_code,
    )


def create_access_token(user: User, session: UserSession) -> str:
    now = utcnow()
    payload = {
        "sub": user.id,
        "sid": session.id,
        "ver": user.token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_session(
    db: Session,
    user: User,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[UserSession, str]:
    raw_token = new_refresh_token()
    row = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_token(raw_token),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(row)
    db.flush()
    return row, raw_token


def rotate_refresh_session(
    db: Session,
    raw_token: str,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, UserSession, str] | None:
    current = db.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash == hash_token(raw_token)
        )
    )
    if (
        current is None
        or current.revoked_at is not None
        or aware(current.expires_at) <= utcnow()
    ):
        return None
    user = db.get(User, current.user_id)
    if user is None or not user.is_active:
        return None
    current.revoked_at = utcnow()
    current.last_used_at = utcnow()
    new_session, new_token = create_session(
        db, user, ip_address=ip_address, user_agent=user_agent
    )
    return user, new_session, new_token


def record_login_attempt(
    db: Session, username: str, ip_address: str | None, success: bool
) -> None:
    db.add(LoginAttempt(username=username, ip_address=ip_address, success=success))


def is_login_locked(db: Session, username: str, ip_address: str | None) -> bool:
    cutoff = utcnow() - timedelta(minutes=settings.login_window_minutes)
    failures = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.username == username,
            LoginAttempt.ip_address == ip_address,
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= cutoff,
        )
    )
    return int(failures or 0) >= settings.login_max_failures


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Нэвтрэлт хүчингүй эсвэл хугацаа дууссан",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "sid", "ver", "type"]},
        )
        if payload.get("type") != "access":
            raise ValueError("wrong token type")
        user_id = str(payload["sub"])
        session_id = str(payload["sid"])
        token_version = int(payload["ver"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc

    user = db.get(User, user_id)
    session = db.get(UserSession, session_id)
    if (
        user is None
        or not user.is_active
        or user.token_version != token_version
        or session is None
        or session.user_id != user.id
        or session.revoked_at is not None
        or aware(session.expires_at) <= utcnow()
    ):
        raise unauthorized
    return auth_user(user, session.id)


def require_owner(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    if user.role != ROLE_OWNER:
        raise HTTPException(
            status_code=403, detail="Энэ үйлдэл зөвхөн малын эзэнд нээлттэй"
        )
    return user


def require_module(module: str) -> Callable[..., AuthUser]:
    def dependency(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        if module not in user.allowed_modules:
            raise HTTPException(
                status_code=403, detail="Танд энэ модулийг ашиглах эрх байхгүй"
            )
        return user

    return dependency
