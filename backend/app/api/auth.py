from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..audit import deserialize, write_audit
from ..auth import (
    MODULE_ANALYTICS,
    MODULE_CATTLE,
    MODULE_HORSES,
    MODULE_SMALL,
    AuthUser,
    auth_user,
    create_access_token,
    create_session,
    get_current_user,
    is_login_locked,
    record_login_attempt,
    require_owner,
    rotate_refresh_session,
)
from ..config import get_settings
from ..database import get_db
from ..models import AuditLog, User, UserSession
from ..schemas import (
    AdminRotateCodeRequest,
    AuditRead,
    ChangeCodeRequest,
    LoginRequest,
    TokenResponse,
    UserInfo,
)
from ..security.hashing import hash_password, verify_password


router = APIRouter(prefix="/api/v1", tags=["authentication"])
settings = get_settings()


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def user_info(user: User | AuthUser, session_id: str | None = None) -> UserInfo:
    current = user if isinstance(user, AuthUser) else auth_user(user, session_id or "")
    return UserInfo(
        id=current.id,
        username=current.username,
        role=current.role,
        allowed_modules=list(current.allowed_modules),
        must_change_code=current.must_change_code,
    )


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="none" if settings.refresh_cookie_secure else "lax",
        path="/api/v1/auth",
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    username = payload.username.strip()
    ip_address = client_ip(request)
    if is_login_locked(db, username, ip_address):
        write_audit(
            db,
            None,
            "LOGIN_BLOCKED",
            request=request,
            username=username,
            role="UNKNOWN",
            detail="Too many failed login attempts",
            success=False,
        )
        db.commit()
        raise HTTPException(
            status_code=429,
            detail="Олон удаа буруу оролдлоо. Түр хүлээгээд дахин оролдоно уу",
        )

    user = db.scalar(select(User).where(User.username == username))
    valid = (
        user is not None
        and user.is_active
        and verify_password(payload.code, user.password_hash)
    )
    record_login_attempt(db, username, ip_address, valid)
    if not valid:
        write_audit(
            db,
            None,
            "LOGIN_FAILED",
            request=request,
            username=username,
            role=user.role if user is not None else "UNKNOWN",
            detail="Invalid credentials or disabled account",
            success=False,
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Нэвтрэх нэр эсвэл код буруу")

    assert user is not None
    session, refresh_token = create_session(
        db,
        user,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )
    user.last_login_at = datetime.now(timezone.utc)
    write_audit(db, user, "LOGIN", request=request, detail="Амжилттай нэвтэрсэн")
    db.commit()
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=create_access_token(user, session),
        expires_in_seconds=settings.access_token_minutes * 60,
        user=user_info(user, session.id),
    )


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: Annotated[
        str | None, Cookie(alias=settings.refresh_cookie_name)
    ] = None,
) -> TokenResponse:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Сессийн мэдээлэл олдсонгүй")
    rotated = rotate_refresh_session(
        db,
        refresh_token,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if rotated is None:
        raise HTTPException(
            status_code=401, detail="Сесс хүчингүй эсвэл хугацаа дууссан"
        )
    user, session, new_token = rotated
    write_audit(
        db,
        user,
        "SESSION_REFRESH",
        request=request,
        entity_type="session",
        entity_id=session.id,
    )
    db.commit()
    set_refresh_cookie(response, new_token)
    return TokenResponse(
        access_token=create_access_token(user, session),
        expires_in_seconds=settings.access_token_minutes * 60,
        user=user_info(user, session.id),
    )


@router.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    session = db.get(UserSession, user.session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
    write_audit(
        db,
        user,
        "LOGOUT",
        request=request,
        entity_type="session",
        entity_id=user.session_id,
    )
    db.commit()
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")
    return {"status": "logged_out"}


@router.get("/auth/me", response_model=UserInfo)
def me(user: AuthUser = Depends(get_current_user)) -> UserInfo:
    return user_info(user)


@router.post("/auth/change-code")
def change_code(
    payload: ChangeCodeRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    row = db.get(User, user.id)
    if row is None or not verify_password(payload.current_code, row.password_hash):
        raise HTTPException(status_code=400, detail="Одоогийн код буруу")
    row.password_hash = hash_password(payload.new_code)
    row.must_change_code = False
    row.token_version += 1
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == row.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    write_audit(
        db,
        user,
        "CREDENTIAL_CHANGED",
        request=request,
        entity_type="user",
        entity_id=row.id,
    )
    db.commit()
    return {"status": "changed", "reauthentication_required": "true"}


@router.get("/users", response_model=list[UserInfo])
def list_users(
    _: AuthUser = Depends(require_owner), db: Session = Depends(get_db)
) -> list[UserInfo]:
    return [
        user_info(row) for row in db.scalars(select(User).order_by(User.username)).all()
    ]


@router.post("/users/{user_id}/rotate-code")
def rotate_code(
    user_id: str,
    payload: AdminRotateCodeRequest,
    request: Request,
    actor: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Хэрэглэгч олдсонгүй")
    row.password_hash = hash_password(payload.new_code)
    row.must_change_code = payload.must_change_code
    row.token_version += 1
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == row.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    write_audit(
        db,
        actor,
        "CREDENTIAL_ROTATED",
        request=request,
        entity_type="user",
        entity_id=row.id,
        detail=row.username,
    )
    db.commit()
    return {"status": "rotated"}


@router.get("/modules")
def modules(
    user: AuthUser = Depends(get_current_user),
) -> dict[str, list[dict[str, str]]]:
    catalog = [
        {"key": MODULE_HORSES, "label": "Адуу"},
        {"key": MODULE_CATTLE, "label": "Үхэр"},
        {"key": MODULE_SMALL, "label": "Хонь"},
        {"key": MODULE_ANALYTICS, "label": "Анализ"},
    ]
    return {
        "modules": [item for item in catalog if item["key"] in user.allowed_modules]
    }


def audit_read(row: AuditLog) -> AuditRead:
    return AuditRead(
        id=row.id,
        actor_user_id=row.actor_user_id,
        username=row.username,
        role=row.role,
        action=row.action,
        module=row.module,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        previous_data=deserialize(row.previous_data),
        new_data=deserialize(row.new_data),
        detail=row.detail,
        request_id=row.request_id,
        ip_address=row.ip_address,
        success=row.success,
        created_at=row.created_at,
    )


@router.get("/audit", response_model=list[AuditRead])
def list_audit(
    _: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
    limit: int = 100,
    username: str | None = None,
    module: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[AuditRead]:
    limit = max(1, min(limit, 500))
    query = select(AuditLog)
    if username:
        query = query.where(AuditLog.username == username)
    if module:
        query = query.where(AuditLog.module == module)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    rows = db.scalars(query.order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [audit_read(row) for row in rows]
