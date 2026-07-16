from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import MODULE_HERDERS, AuthUser, require_owner
from ..database import get_db
from ..models import Herder, User
from ..schemas import HerderCreate, HerderUpdate, RestoreRequest
from ..services.domain import model_snapshot, require_version


router = APIRouter(prefix="/api/v1/herders", tags=["herders"])


def mask_registration(value: str) -> str:
    return "•" * max(0, len(value) - 4) + value[-4:]


def safe_snapshot(row: Herder) -> dict[str, Any]:
    data = model_snapshot(row)
    data["registration_number"] = mask_registration(row.registration_number)
    return data


def herder_read(row: Herder, db: Session) -> dict[str, Any]:
    creator = db.get(User, row.created_by)
    updater = db.get(User, row.updated_by)
    return {
        **model_snapshot(row),
        "registration_number_masked": mask_registration(row.registration_number),
        "created_by_name": creator.username if creator else "—",
        "updated_by_name": updater.username if updater else "—",
    }


@router.get("")
def list_herders(
    include_archived: bool = False,
    module: str | None = None,
    _: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(Herder)
    if not include_archived:
        query = query.where(Herder.is_active.is_(True))
    if module:
        query = query.where(Herder.module == module)
    rows = db.scalars(query.order_by(Herder.module, Herder.first_name)).all()
    return [herder_read(row, db) for row in rows]


@router.post("")
def create_herder(
    payload: HerderCreate,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.ended_date and payload.ended_date < payload.started_date:
        raise HTTPException(
            status_code=400, detail="Дууссан огноо эхэлсэн огнооноос өмнө байж болохгүй"
        )
    if db.scalar(
        select(Herder).where(
            func.lower(Herder.registration_number)
            == payload.registration_number.strip().lower()
        )
    ):
        raise HTTPException(
            status_code=409, detail="Энэ регистрийн дугаар бүртгэлтэй байна"
        )
    data = payload.model_dump()
    data["registration_number"] = payload.registration_number.strip()
    row = Herder(
        **data,
        is_active=payload.ended_date is None,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        user,
        "CREATE",
        request=request,
        module=MODULE_HERDERS,
        entity_type="herder",
        entity_id=row.id,
        new_data=safe_snapshot(row),
    )
    db.commit()
    return herder_read(row, db)


@router.patch("/{herder_id}")
def update_herder(
    herder_id: str,
    payload: HerderUpdate,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(Herder, herder_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Малчин олдсонгүй")
    require_version(row, payload.expected_version)
    if payload.ended_date and payload.ended_date < payload.started_date:
        raise HTTPException(
            status_code=400, detail="Дууссан огноо эхэлсэн огнооноос өмнө байж болохгүй"
        )
    duplicate = db.scalar(
        select(Herder).where(
            func.lower(Herder.registration_number)
            == payload.registration_number.strip().lower(),
            Herder.id != row.id,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409, detail="Энэ регистрийн дугаар бүртгэлтэй байна"
        )
    before = safe_snapshot(row)
    for field, value in payload.model_dump(exclude={"expected_version"}).items():
        setattr(row, field, value)
    row.registration_number = row.registration_number.strip()
    row.is_active = row.ended_date is None and row.archived_at is None
    row.updated_by = user.id
    row.version += 1
    write_audit(
        db,
        user,
        "UPDATE",
        request=request,
        module=MODULE_HERDERS,
        entity_type="herder",
        entity_id=row.id,
        previous_data=before,
        new_data=safe_snapshot(row),
    )
    db.commit()
    return herder_read(row, db)


@router.post("/{herder_id}/archive")
def archive_herder(
    herder_id: str,
    payload: RestoreRequest,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(Herder, herder_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Малчин олдсонгүй")
    before = safe_snapshot(row)
    row.archived_at = datetime.now(timezone.utc)
    row.ended_date = row.ended_date or datetime.now(timezone.utc).date()
    row.is_active = False
    row.updated_by = user.id
    row.version += 1
    write_audit(
        db,
        user,
        "ARCHIVE",
        request=request,
        module=MODULE_HERDERS,
        entity_type="herder",
        entity_id=row.id,
        previous_data=before,
        new_data=safe_snapshot(row),
        detail=payload.reason,
    )
    db.commit()
    return herder_read(row, db)


@router.post("/{herder_id}/restore")
def restore_herder(
    herder_id: str,
    payload: RestoreRequest,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(Herder, herder_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Малчин олдсонгүй")
    if row.archived_at is None:
        raise HTTPException(status_code=409, detail="Малчин архивт байхгүй")
    before = safe_snapshot(row)
    row.archived_at = None
    row.ended_date = None
    row.is_active = True
    row.updated_by = user.id
    row.version += 1
    write_audit(
        db,
        user,
        "RESTORE",
        request=request,
        module=MODULE_HERDERS,
        entity_type="herder",
        entity_id=row.id,
        previous_data=before,
        new_data=safe_snapshot(row),
        detail=payload.reason,
    )
    db.commit()
    return herder_read(row, db)
