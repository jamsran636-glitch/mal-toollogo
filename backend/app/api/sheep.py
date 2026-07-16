from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import MODULE_SMALL, AuthUser, require_module, require_owner
from ..database import get_db
from ..models import Herder, SmallLivestockCount, SmallLivestockLoss, User
from ..schemas import (
    SmallCountCreate,
    SmallCountUpdate,
    SmallLossCreate,
    SmallLossUpdate,
)
from ..services.domain import model_snapshot, require_version, small_count_dict
from ..services.idempotency import remember, replay


router = APIRouter(prefix="/api/v1/small-livestock", tags=["small livestock"])
small_access = require_module(MODULE_SMALL)


def count_read(row: SmallLivestockCount, db: Session) -> dict[str, Any]:
    result = small_count_dict(row)
    creator = db.get(User, row.created_by)
    updater = db.get(User, row.updated_by)
    result["created_by_name"] = creator.username if creator else "—"
    result["updated_by_name"] = updater.username if updater else "—"
    return result


def loss_read(row: SmallLivestockLoss, db: Session) -> dict[str, Any]:
    herder = db.get(Herder, row.herder_id) if row.herder_id else None
    creator = db.get(User, row.created_by)
    return {
        **model_snapshot(row),
        "herder_name": f"{herder.last_name} {herder.first_name}" if herder else None,
        "created_by_name": creator.username if creator else "—",
    }


@router.get("/access")
def access(user: AuthUser = Depends(small_access)) -> dict[str, str]:
    return {"status": "allowed", "module": MODULE_SMALL, "username": user.username}


@router.get("/counts")
def list_counts(
    _: AuthUser = Depends(small_access), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(SmallLivestockCount).order_by(
            SmallLivestockCount.count_date.desc(), SmallLivestockCount.created_at.desc()
        )
    ).all()
    return [count_read(row, db) for row in rows]


@router.get("/current")
def current(
    _: AuthUser = Depends(small_access), db: Session = Depends(get_db)
) -> dict[str, Any]:
    row = db.scalar(
        select(SmallLivestockCount)
        .where(SmallLivestockCount.count_type == "FULL")
        .order_by(
            SmallLivestockCount.count_date.desc(), SmallLivestockCount.created_at.desc()
        )
    )
    if row is None:
        return {
            "total": 0,
            "sheep_total": 0,
            "goat_total": 0,
            "male_sheep_total": 0,
            "female_sheep_total": 0,
            "male_goat_total": 0,
            "female_goat_total": 0,
            "lamb_total": 0,
            "kid_total": 0,
            "adult_total": 0,
        }
    return count_read(row, db)


@router.post("/counts")
def create_count(
    payload: SmallCountCreate,
    request: Request,
    user: AuthUser = Depends(small_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    data = payload.model_dump(mode="json")
    key, cached = replay(db, user, request, data)
    if cached is not None:
        return cached
    duplicate = db.scalar(
        select(SmallLivestockCount).where(
            SmallLivestockCount.count_type == payload.count_type,
            SmallLivestockCount.count_date == payload.count_date,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Энэ өдөр ижил төрлийн тооллого байна. Засвар үйлдлийг ашиглана уу",
        )
    row = SmallLivestockCount(
        **payload.model_dump(), created_by=user.id, updated_by=user.id
    )
    db.add(row)
    db.flush()
    result = count_read(row, db)
    write_audit(
        db,
        user,
        "CREATE",
        request=request,
        module=MODULE_SMALL,
        entity_type="census",
        entity_id=row.id,
        new_data=result,
        detail="Бүрэн тооллого" if row.count_type == "FULL" else "Оройн тоо",
    )
    remember(db, user, request, key, data, result)
    db.commit()
    return result


@router.patch("/counts/{count_id}")
def correct_count(
    count_id: str,
    payload: SmallCountUpdate,
    request: Request,
    user: AuthUser = Depends(small_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(SmallLivestockCount, count_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Тооллого олдсонгүй")
    require_version(row, payload.expected_version)
    duplicate = db.scalar(
        select(SmallLivestockCount).where(
            SmallLivestockCount.count_type == payload.count_type,
            SmallLivestockCount.count_date == payload.count_date,
            SmallLivestockCount.id != row.id,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409, detail="Энэ өдөр ижил төрлийн өөр тооллого байна"
        )
    before = count_read(row, db)
    changes = payload.model_dump(exclude={"expected_version", "correction_reason"})
    for field, value in changes.items():
        setattr(row, field, value)
    row.updated_by = user.id
    row.version += 1
    after = count_read(row, db)
    write_audit(
        db,
        user,
        "CORRECT",
        request=request,
        module=MODULE_SMALL,
        entity_type="census",
        entity_id=row.id,
        previous_data=before,
        new_data=after,
        detail=payload.correction_reason,
    )
    db.commit()
    return after


@router.get("/losses")
def list_losses(
    _: AuthUser = Depends(require_owner), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(SmallLivestockLoss).order_by(
            SmallLivestockLoss.loss_date.desc(), SmallLivestockLoss.created_at.desc()
        )
    ).all()
    return [loss_read(row, db) for row in rows]


@router.post("/losses")
def create_loss(
    payload: SmallLossCreate,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.herder_id and db.get(Herder, payload.herder_id) is None:
        raise HTTPException(status_code=404, detail="Малчин олдсонгүй")
    row = SmallLivestockLoss(
        **payload.model_dump(), created_by=user.id, updated_by=user.id
    )
    db.add(row)
    db.flush()
    result = loss_read(row, db)
    write_audit(
        db,
        user,
        "CREATE",
        request=request,
        module=MODULE_SMALL,
        entity_type="mortality",
        entity_id=row.id,
        new_data=result,
    )
    db.commit()
    return result


@router.patch("/losses/{loss_id}")
def update_loss(
    loss_id: str,
    payload: SmallLossUpdate,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(SmallLivestockLoss, loss_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Хорогдлын бүртгэл олдсонгүй")
    require_version(row, payload.expected_version)
    if payload.herder_id and db.get(Herder, payload.herder_id) is None:
        raise HTTPException(status_code=404, detail="Малчин олдсонгүй")
    before = loss_read(row, db)
    for field, value in payload.model_dump(exclude={"expected_version"}).items():
        setattr(row, field, value)
    row.updated_by = user.id
    row.version += 1
    after = loss_read(row, db)
    write_audit(
        db,
        user,
        "UPDATE",
        request=request,
        module=MODULE_SMALL,
        entity_type="mortality",
        entity_id=row.id,
        previous_data=before,
        new_data=after,
    )
    db.commit()
    return after
