import hashlib
import json
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..auth import AuthUser
from ..models import IdempotencyRecord


def request_fingerprint(endpoint: str, payload: Any) -> str:
    encoded = json.dumps(
        {"endpoint": endpoint, "payload": payload}, sort_keys=True, default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def replay(
    db: Session,
    user: AuthUser,
    request: Request,
    payload: Any,
) -> tuple[str | None, dict[str, Any] | list[Any] | None]:
    key = request.headers.get("idempotency-key")
    if not key:
        return None, None
    if len(key) > 100:
        raise HTTPException(status_code=400, detail="Idempotency-Key хэт урт байна")
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Serialize the first writer for this user/key for the duration of the
        # transaction. The waiting request then observes and replays the row
        # committed by the winner instead of racing the unique constraint.
        lock_id = int.from_bytes(
            hashlib.sha256(f"{user.id}:{key}".encode()).digest()[:8],
            byteorder="big",
            signed=True,
        )
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user.id, IdempotencyRecord.key == key
        )
    )
    fingerprint = request_fingerprint(request.url.path, payload)
    if existing is None:
        return key, None
    if existing.endpoint != request.url.path or existing.request_hash != fingerprint:
        raise HTTPException(
            status_code=409, detail="Энэ давтагдашгүй түлхүүр өөр хүсэлтэд ашиглагдсан"
        )
    return key, json.loads(existing.response_json)


def remember(
    db: Session,
    user: AuthUser,
    request: Request,
    key: str | None,
    payload: Any,
    response: Any,
) -> None:
    if not key:
        return
    db.add(
        IdempotencyRecord(
            user_id=user.id,
            key=key,
            endpoint=request.url.path,
            request_hash=request_fingerprint(request.url.path, payload),
            response_json=json.dumps(response, ensure_ascii=False, default=str),
            status_code=200,
        )
    )
