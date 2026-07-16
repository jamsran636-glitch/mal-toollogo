import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .auth import AuthUser
from .models import AuditLog, User


def serialize(value: object) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def deserialize(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def request_context(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {"request_id": None, "ip_address": None, "user_agent": None}
    return {
        "request_id": getattr(request.state, "request_id", None),
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent", "")[:500] or None,
    }


def write_audit(
    db: Session,
    actor: AuthUser | User | None,
    action: str,
    *,
    request: Request | None = None,
    username: str | None = None,
    role: str | None = None,
    module: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    previous_data: object = None,
    new_data: object = None,
    detail: str | None = None,
    success: bool = True,
) -> AuditLog:
    """Add an immutable server-authored audit row without committing.

    The caller must commit the business mutation and this audit row together.
    """
    context = request_context(request)
    row = AuditLog(
        actor_user_id=actor.id if actor is not None else None,
        username=actor.username if actor is not None else (username or "UNKNOWN"),
        role=actor.role if actor is not None else (role or "UNKNOWN"),
        action=action,
        module=module,
        entity_type=entity_type,
        entity_id=entity_id,
        previous_data=serialize(previous_data),
        new_data=serialize(new_data),
        detail=detail,
        request_id=context["request_id"],
        ip_address=context["ip_address"],
        user_agent=context["user_agent"],
        success=success,
    )
    db.add(row)
    return row
