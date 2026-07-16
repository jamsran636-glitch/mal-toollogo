from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import MODULE_FINANCE, AuthUser, require_owner
from ..database import get_db
from ..models import FinanceEntry, User
from ..schemas import ArchiveRequest, FinanceCreate, FinanceUpdate, RestoreRequest
from ..services.domain import model_snapshot, require_version
from ..services.idempotency import remember, replay


router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


def finance_read(row: FinanceEntry, db: Session) -> dict[str, Any]:
    creator = db.get(User, row.created_by)
    updater = db.get(User, row.updated_by)
    return {
        **model_snapshot(row),
        "created_by_name": creator.username if creator else "—",
        "updated_by_name": updater.username if updater else "—",
    }


@router.get("")
def list_finance(
    include_archived: bool = False,
    year: int | None = None,
    entry_type: str | None = None,
    _: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(FinanceEntry)
    if not include_archived:
        query = query.where(FinanceEntry.archived_at.is_(None))
    if year:
        query = query.where(
            FinanceEntry.entry_date >= datetime(year, 1, 1).date(),
            FinanceEntry.entry_date <= datetime(year, 12, 31).date(),
        )
    if entry_type:
        if entry_type not in {"INCOME", "EXPENSE"}:
            raise HTTPException(status_code=400, detail="Санхүүгийн төрөл буруу")
        query = query.where(FinanceEntry.entry_type == entry_type)
    rows = db.scalars(
        query.order_by(FinanceEntry.entry_date.desc(), FinanceEntry.created_at.desc())
    ).all()
    return [finance_read(row, db) for row in rows]


@router.post("")
def create_finance(
    payload: FinanceCreate,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    data = payload.model_dump(mode="json")
    key, cached = replay(db, user, request, data)
    if cached is not None:
        return cached
    row = FinanceEntry(**payload.model_dump(), created_by=user.id, updated_by=user.id)
    db.add(row)
    db.flush()
    result = finance_read(row, db)
    write_audit(
        db,
        user,
        "CREATE",
        request=request,
        module=MODULE_FINANCE,
        entity_type="finance",
        entity_id=row.id,
        new_data=result,
    )
    remember(db, user, request, key, data, result)
    db.commit()
    return result


@router.patch("/{entry_id}")
def update_finance(
    entry_id: str,
    payload: FinanceUpdate,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(FinanceEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Санхүүгийн бичлэг олдсонгүй")
    if row.archived_at is not None:
        raise HTTPException(
            status_code=409, detail="Архивын бичлэгийг эхлээд сэргээнэ үү"
        )
    require_version(row, payload.expected_version)
    before = finance_read(row, db)
    for field, value in payload.model_dump(exclude={"expected_version"}).items():
        setattr(row, field, value)
    row.updated_by = user.id
    row.version += 1
    after = finance_read(row, db)
    write_audit(
        db,
        user,
        "UPDATE",
        request=request,
        module=MODULE_FINANCE,
        entity_type="finance",
        entity_id=row.id,
        previous_data=before,
        new_data=after,
    )
    db.commit()
    return after


@router.post("/{entry_id}/archive")
def archive_finance(
    entry_id: str,
    payload: ArchiveRequest,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(FinanceEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Санхүүгийн бичлэг олдсонгүй")
    if row.archived_at is not None:
        raise HTTPException(status_code=409, detail="Бичлэг аль хэдийн архивлагдсан")
    before = finance_read(row, db)
    row.archived_at = datetime.now(timezone.utc)
    row.archive_note = payload.archive_note
    row.updated_by = user.id
    row.version += 1
    after = finance_read(row, db)
    write_audit(
        db,
        user,
        "ARCHIVE",
        request=request,
        module=MODULE_FINANCE,
        entity_type="finance",
        entity_id=row.id,
        previous_data=before,
        new_data=after,
        detail=payload.archive_note,
    )
    db.commit()
    return after


@router.post("/{entry_id}/restore")
def restore_finance(
    entry_id: str,
    payload: RestoreRequest,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(FinanceEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Санхүүгийн бичлэг олдсонгүй")
    if row.archived_at is None:
        raise HTTPException(status_code=409, detail="Бичлэг архивт байхгүй")
    before = finance_read(row, db)
    row.archived_at = None
    row.archive_note = None
    row.updated_by = user.id
    row.version += 1
    after = finance_read(row, db)
    write_audit(
        db,
        user,
        "RESTORE",
        request=request,
        module=MODULE_FINANCE,
        entity_type="finance",
        entity_id=row.id,
        previous_data=before,
        new_data=after,
        detail=payload.reason,
    )
    db.commit()
    return after
