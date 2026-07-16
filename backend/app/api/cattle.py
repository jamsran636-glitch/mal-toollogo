from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import MODULE_CATTLE, AuthUser, require_module
from ..database import get_db
from ..models import Cattle, ImageAsset
from ..schemas import (
    ArchiveRequest,
    CattleCreate,
    CattleRead,
    CattleUpdate,
    HorseStatistics,
    ImageRead,
    RestoreRequest,
)
from ..services.domain import (
    age_years,
    cattle_age_category,
    model_snapshot,
    require_version,
    validate_birth_year,
    validate_cattle_state,
)
from ..services.idempotency import remember, replay
from ..services.storage import (
    create_image_set,
    delete_object,
    prepare_upload,
    signed_proxy_url,
)


router = APIRouter(prefix="/api/v1/cattle", tags=["cattle"])
cattle_access = require_module(MODULE_CATTLE)
logger = logging.getLogger(__name__)


def image_read(asset: ImageAsset) -> ImageRead:
    return ImageRead(
        id=asset.id,
        kind=asset.kind,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        created_at=asset.created_at,
        url=signed_proxy_url(asset.id),
    )


def cattle_read(row: Cattle, db: Session) -> CattleRead:
    mother = db.get(Cattle, row.mother_id) if row.mother_id else None
    assets = db.scalars(
        select(ImageAsset)
        .where(ImageAsset.owner_type == "cattle", ImageAsset.owner_id == row.id)
        .order_by(ImageAsset.kind, ImageAsset.created_at)
    ).all()
    years = age_years(row.birth_year)
    return CattleRead(
        id=row.id,
        ear_tag=row.ear_tag,
        color=row.color,
        birth_year=row.birth_year,
        age_years=years,
        age_category=cattle_age_category(years, row.sex),
        sex=row.sex,
        is_bull=row.is_bull,
        current_status=row.current_status,
        mother_id=row.mother_id,
        mother_label=f"{mother.ear_tag} · {mother.color}" if mother else None,
        additional_info=row.additional_info,
        archived_at=row.archived_at,
        archive_note=row.archive_note,
        unnatural_loss=row.unnatural_loss,
        version=row.version,
        images=[image_read(asset) for asset in assets],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/access")
def access(user: AuthUser = Depends(cattle_access)) -> dict[str, str]:
    return {"status": "allowed", "module": MODULE_CATTLE, "username": user.username}


@router.get("/statistics", response_model=HorseStatistics)
def statistics(
    _: AuthUser = Depends(cattle_access), db: Session = Depends(get_db)
) -> HorseStatistics:
    rows = list(
        db.scalars(select(Cattle).where(Cattle.current_status == "ACTIVE")).all()
    )
    return HorseStatistics(
        total=len(rows),
        eligible_males=sum(
            1
            for row in rows
            if row.sex == "MALE" and not row.is_bull and age_years(row.birth_year) >= 1
        ),
        eligible_females=sum(
            1 for row in rows if row.sex == "FEMALE" and age_years(row.birth_year) >= 2
        ),
        offspring=sum(1 for row in rows if age_years(row.birth_year) == 0),
        breeding_males=sum(1 for row in rows if row.is_bull),
    )


@router.get("", response_model=list[CattleRead])
def list_cattle(
    status_filter: str = "ACTIVE",
    search: str | None = None,
    _: AuthUser = Depends(cattle_access),
    db: Session = Depends(get_db),
) -> list[CattleRead]:
    query = select(Cattle)
    if status_filter == "ACTIVE":
        query = query.where(Cattle.current_status == "ACTIVE")
    elif status_filter == "ARCHIVED":
        query = query.where(Cattle.current_status.in_(("ARCHIVED", "DECEASED")))
    elif status_filter != "ALL":
        raise HTTPException(status_code=400, detail="Төлөв шүүлт буруу")
    if search:
        term = f"%{search.strip()}%"
        query = query.where(Cattle.ear_tag.ilike(term) | Cattle.color.ilike(term))
    rows = list(db.scalars(query).all())
    active_rows = [row for row in rows if row.current_status == "ACTIVE"]

    def ordering(row: Cattle) -> tuple[int, int, str]:
        years = age_years(row.birth_year)
        if row.current_status != "ACTIVE":
            return (4, years, row.ear_tag)
        if row.is_bull:
            return (0, 0, row.ear_tag)
        has_calf = row.sex == "FEMALE" and any(
            child.mother_id == row.id and age_years(child.birth_year) == 0
            for child in active_rows
        )
        if has_calf:
            return (1, 0, row.ear_tag)
        if row.sex == "FEMALE":
            return (2, years, row.ear_tag)
        return (3, years, row.ear_tag)

    return [cattle_read(row, db) for row in sorted(rows, key=ordering)]


@router.post("", response_model=CattleRead)
def create_cattle(
    payload: CattleCreate,
    request: Request,
    user: AuthUser = Depends(cattle_access),
    db: Session = Depends(get_db),
) -> CattleRead | dict[str, Any]:
    data = payload.model_dump()
    key, cached = replay(db, user, request, data)
    if cached is not None:
        return cached
    validate_birth_year(payload.birth_year)
    validate_cattle_state(
        db,
        sex=payload.sex,
        is_bull=payload.is_bull,
        birth_year=payload.birth_year,
        mother_id=payload.mother_id,
    )
    if db.scalar(
        select(Cattle).where(
            func.lower(Cattle.ear_tag) == payload.ear_tag.strip().lower()
        )
    ):
        raise HTTPException(
            status_code=409, detail="Энэ ээмэгний дугаар бүртгэлтэй байна"
        )
    data["ear_tag"] = payload.ear_tag.strip()
    row = Cattle(**data, created_by=user.id, updated_by=user.id)
    db.add(row)
    db.flush()
    write_audit(
        db,
        user,
        "CREATE",
        request=request,
        module=MODULE_CATTLE,
        entity_type="cattle",
        entity_id=row.id,
        new_data=model_snapshot(row),
    )
    result = cattle_read(row, db).model_dump()
    remember(db, user, request, key, data, result)
    db.commit()
    return CattleRead.model_validate(result)


@router.get("/{cattle_id}", response_model=CattleRead)
def get_cattle(
    cattle_id: str, _: AuthUser = Depends(cattle_access), db: Session = Depends(get_db)
) -> CattleRead:
    row = db.get(Cattle, cattle_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Үхэр олдсонгүй")
    return cattle_read(row, db)


@router.patch("/{cattle_id}", response_model=CattleRead)
def update_cattle(
    cattle_id: str,
    payload: CattleUpdate,
    request: Request,
    user: AuthUser = Depends(cattle_access),
    db: Session = Depends(get_db),
) -> CattleRead:
    row = db.get(Cattle, cattle_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Үхэр олдсонгүй")
    if row.current_status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Архивын үхрийг эхлээд сэргээнэ үү")
    require_version(row, payload.expected_version)
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    state = {
        field: changes.get(field, getattr(row, field))
        for field in (
            "ear_tag",
            "color",
            "birth_year",
            "sex",
            "is_bull",
            "mother_id",
            "additional_info",
        )
    }
    validate_cattle_state(
        db,
        sex=state["sex"],
        is_bull=state["is_bull"],
        birth_year=state["birth_year"],
        mother_id=state["mother_id"],
        cattle_id=row.id,
    )
    duplicate = db.scalar(
        select(Cattle).where(
            func.lower(Cattle.ear_tag) == state["ear_tag"].strip().lower(),
            Cattle.id != row.id,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409, detail="Энэ ээмэгний дугаар бүртгэлтэй байна"
        )
    state["ear_tag"] = state["ear_tag"].strip()
    before = model_snapshot(row)
    for field, value in state.items():
        setattr(row, field, value)
    row.updated_by = user.id
    row.version += 1
    write_audit(
        db,
        user,
        "UPDATE",
        request=request,
        module=MODULE_CATTLE,
        entity_type="cattle",
        entity_id=row.id,
        previous_data=before,
        new_data=model_snapshot(row),
    )
    db.commit()
    return cattle_read(row, db)


@router.post("/{cattle_id}/archive", response_model=CattleRead)
def archive_cattle(
    cattle_id: str,
    payload: ArchiveRequest,
    request: Request,
    user: AuthUser = Depends(cattle_access),
    db: Session = Depends(get_db),
) -> CattleRead:
    row = db.get(Cattle, cattle_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Үхэр олдсонгүй")
    if row.current_status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Үхэр аль хэдийн архивлагдсан")
    before = model_snapshot(row)
    row.current_status = "DECEASED" if payload.deceased else "ARCHIVED"
    row.archived_at = datetime.now(timezone.utc)
    row.archive_note = payload.archive_note
    row.unnatural_loss = payload.unnatural_loss
    row.updated_by = user.id
    row.version += 1
    write_audit(
        db,
        user,
        "ARCHIVE",
        request=request,
        module=MODULE_CATTLE,
        entity_type="cattle",
        entity_id=row.id,
        previous_data=before,
        new_data=model_snapshot(row),
        detail=payload.archive_note,
    )
    db.commit()
    return cattle_read(row, db)


@router.post("/{cattle_id}/restore", response_model=CattleRead)
def restore_cattle(
    cattle_id: str,
    payload: RestoreRequest,
    request: Request,
    user: AuthUser = Depends(cattle_access),
    db: Session = Depends(get_db),
) -> CattleRead:
    row = db.get(Cattle, cattle_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Үхэр олдсонгүй")
    if row.current_status not in {"ARCHIVED", "DECEASED"}:
        raise HTTPException(status_code=409, detail="Үхэр архивт байхгүй")
    before = model_snapshot(row)
    row.current_status = "ACTIVE"
    row.archived_at = None
    row.archive_note = None
    row.unnatural_loss = False
    row.updated_by = user.id
    row.version += 1
    write_audit(
        db,
        user,
        "RESTORE",
        request=request,
        module=MODULE_CATTLE,
        entity_type="cattle",
        entity_id=row.id,
        previous_data=before,
        new_data=model_snapshot(row),
        detail=payload.reason,
    )
    db.commit()
    return cattle_read(row, db)


@router.post("/{cattle_id}/images", response_model=CattleRead)
async def replace_images(
    cattle_id: str,
    request: Request,
    files: list[UploadFile] = File(...),
    user: AuthUser = Depends(cattle_access),
    db: Session = Depends(get_db),
) -> CattleRead:
    row = db.get(Cattle, cattle_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Үхэр олдсонгүй")
    prepared = [await prepare_upload(file) for file in files]
    old_assets = list(
        db.scalars(
            select(ImageAsset).where(
                ImageAsset.owner_type == "cattle", ImageAsset.owner_id == row.id
            )
        ).all()
    )
    new_assets, old_keys = create_image_set(
        db, owner_type="cattle", owner_id=row.id, uploads=prepared, created_by=user.id
    )
    row.main_image_id = next(asset.id for asset in new_assets if asset.kind == "MAIN")
    row.layout_image_id = next(
        asset.id for asset in new_assets if asset.kind == "LAYOUT"
    )
    row.updated_by = user.id
    row.version += 1
    db.flush()
    for asset in old_assets:
        db.delete(asset)
    write_audit(
        db,
        user,
        "IMAGE_REPLACE",
        request=request,
        module=MODULE_CATTLE,
        entity_type="cattle",
        entity_id=row.id,
        previous_data=[
            {"id": asset.id, "kind": asset.kind, "filename": asset.original_filename}
            for asset in old_assets
        ],
        new_data=[
            {"id": asset.id, "kind": asset.kind, "filename": asset.original_filename}
            for asset in new_assets
        ],
    )
    db.commit()
    for key in old_keys:
        try:
            delete_object(key)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("orphan image cleanup failed key=%s error=%s", key, exc)
    return cattle_read(row, db)
