from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
import httpx
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import MODULE_HORSES, AuthUser, require_module, require_owner
from ..database import get_db
from ..models import Horse, HorseGroup, HorseGroupTransfer, ImageAsset
from ..schemas import (
    ArchiveRequest,
    HorseCreate,
    HorseGroupCreate,
    HorseGroupRead,
    HorseGroupUpdate,
    HorseRead,
    HorseStatistics,
    HorseTransferRead,
    HorseTransferRequest,
    HorseUpdate,
    ImageRead,
    PermanentDeleteRequest,
    RestoreRequest,
)
from ..services.deletion import image_references, image_snapshot, owned_assets
from ..services.domain import (
    LIVING_HORSE_STATUSES,
    age_years,
    horse_age_category,
    horse_label,
    model_snapshot,
    require_version,
    validate_birth_year,
    validate_horse_links,
)
from ..services.idempotency import remember, replay
from ..services.storage import (
    create_image_set,
    delete_object,
    prepare_upload,
    signed_proxy_url,
)


router = APIRouter(prefix="/api/v1/horses", tags=["horses"])
horse_access = require_module(MODULE_HORSES)
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


def horse_read(
    row: Horse, db: Session, *, indent: int = 0, relation_note: str | None = None
) -> HorseRead:
    group = db.get(HorseGroup, row.group_id)
    mother = db.get(Horse, row.mother_id) if row.mother_id else None
    father = db.get(Horse, row.father_id) if row.father_id else None
    assets = db.scalars(
        select(ImageAsset)
        .where(ImageAsset.owner_type == "horse", ImageAsset.owner_id == row.id)
        .order_by(ImageAsset.kind, ImageAsset.created_at)
    ).all()
    image_rows = [image_read(asset) for asset in assets]
    main_image = next(
        (image for image in image_rows if image.id == row.main_image_id), None
    )
    layout_image = next(
        (image for image in image_rows if image.id == row.layout_image_id), None
    )
    years = age_years(row.birth_year)
    return HorseRead(
        id=row.id,
        group_id=row.group_id,
        group_name=group.name if group else "—",
        color=row.color,
        birth_year=row.birth_year,
        age_years=years,
        age_category=horse_age_category(years),
        display_label=horse_label(row),
        sex=row.sex,
        male_status=row.male_status,
        current_status=row.current_status,
        mother_id=row.mother_id,
        mother_label=horse_label(mother) if mother else None,
        father_id=row.father_id,
        father_label=horse_label(father) if father else None,
        additional_info=row.additional_info,
        archived_at=row.archived_at,
        archive_note=row.archive_note,
        unnatural_loss=row.unnatural_loss,
        version=row.version,
        images=image_rows,
        main_image=main_image,
        layout_image=layout_image,
        created_at=row.created_at,
        updated_at=row.updated_at,
        indent=indent,
        relation_note=relation_note,
    )


@router.get("/access")
def access(user: AuthUser = Depends(horse_access)) -> dict[str, str]:
    return {"status": "allowed", "module": MODULE_HORSES, "username": user.username}


@router.post("/groups", response_model=HorseGroupRead)
def create_group(
    payload: HorseGroupCreate,
    request: Request,
    user: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> HorseGroup:
    name = payload.name.strip()
    if db.scalar(select(HorseGroup).where(func.lower(HorseGroup.name) == name.lower())):
        raise HTTPException(status_code=409, detail="Ийм нэртэй азарганы бүлэг байна")
    row = HorseGroup(
        name=name,
        description=payload.description,
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
        module=MODULE_HORSES,
        entity_type="horse_group",
        entity_id=row.id,
        new_data=model_snapshot(row),
    )
    db.commit()
    return row


@router.get("/groups", response_model=list[HorseGroupRead])
def list_groups(
    include_inactive: bool = False,
    _: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> list[HorseGroup]:
    query = select(HorseGroup)
    if not include_inactive:
        query = query.where(HorseGroup.is_active.is_(True))
    return list(db.scalars(query.order_by(HorseGroup.name)).all())


@router.patch("/groups/{group_id}", response_model=HorseGroupRead)
def update_group(
    group_id: str,
    payload: HorseGroupUpdate,
    request: Request,
    user: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> HorseGroup:
    row = db.get(HorseGroup, group_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Бүлэг олдсонгүй")
    require_version(row, payload.expected_version)
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if changes.get("is_active") is False:
        living = db.scalar(
            select(func.count())
            .select_from(Horse)
            .where(
                Horse.group_id == group_id,
                Horse.current_status.in_(LIVING_HORSE_STATUSES),
            )
        )
        if living:
            raise HTTPException(
                status_code=409, detail="Идэвхтэй адуутай бүлгийг хаах боломжгүй"
            )
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        duplicate = db.scalar(
            select(HorseGroup).where(
                func.lower(HorseGroup.name) == changes["name"].lower(),
                HorseGroup.id != group_id,
            )
        )
        if duplicate:
            raise HTTPException(
                status_code=409, detail="Ийм нэртэй азарганы бүлэг байна"
            )
    before = model_snapshot(row)
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_by = user.id
    row.version += 1
    write_audit(
        db,
        user,
        "UPDATE",
        request=request,
        module=MODULE_HORSES,
        entity_type="horse_group",
        entity_id=row.id,
        previous_data=before,
        new_data=model_snapshot(row),
    )
    db.commit()
    return row


@router.get("/statistics", response_model=HorseStatistics)
def statistics(
    _: AuthUser = Depends(horse_access), db: Session = Depends(get_db)
) -> HorseStatistics:
    rows = list(
        db.scalars(
            select(Horse).where(Horse.current_status.in_(LIVING_HORSE_STATUSES))
        ).all()
    )
    return HorseStatistics(
        total=len(rows),
        eligible_males=sum(
            1
            for row in rows
            if row.sex == "MALE"
            and age_years(row.birth_year) >= 1
            and row.male_status != "STALLION"
        ),
        eligible_females=sum(
            1 for row in rows if row.sex == "FEMALE" and age_years(row.birth_year) >= 2
        ),
        offspring=sum(1 for row in rows if age_years(row.birth_year) == 0),
        breeding_males=sum(1 for row in rows if row.male_status == "STALLION"),
    )


@router.get("/tree")
def tree(
    _: AuthUser = Depends(horse_access), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    groups = db.scalars(
        select(HorseGroup)
        .where(HorseGroup.is_active.is_(True))
        .order_by(HorseGroup.name)
    ).all()
    for group in groups:
        rows = list(
            db.scalars(
                select(Horse).where(
                    Horse.group_id == group.id,
                    Horse.current_status.in_(LIVING_HORSE_STATUSES),
                )
            ).all()
        )
        stallions = sorted(
            (row for row in rows if row.male_status == "STALLION"),
            key=lambda item: item.color,
        )
        mares = sorted(
            (
                row
                for row in rows
                if row.sex == "FEMALE" and age_years(row.birth_year) >= 2
            ),
            key=lambda item: item.color,
        )
        children: dict[str, list[Horse]] = {}
        for row in rows:
            if row.mother_id:
                children.setdefault(row.mother_id, []).append(row)
        used: set[str] = set()
        ordered: list[HorseRead] = []
        for row in stallions:
            ordered.append(horse_read(row, db, relation_note="Азарга"))
            used.add(row.id)
        for mare in mares:
            if mare.id in used:
                continue
            ordered.append(horse_read(mare, db, relation_note="Гүү"))
            used.add(mare.id)
            foals = [
                row
                for row in children.get(mare.id, [])
                if row.group_id == group.id and age_years(row.birth_year) == 0
            ]
            for foal in sorted(
                foals, key=lambda item: (item.birth_year, item.color), reverse=True
            ):
                ordered.append(
                    horse_read(
                        foal, db, indent=1, relation_note=f"{horse_label(mare)}-ийн төл"
                    )
                )
                used.add(foal.id)
        remaining = [row for row in rows if row.id not in used]
        remaining.sort(
            key=lambda item: (item.mother_id is not None, item.birth_year, item.color)
        )
        for row in remaining:
            ordered.append(
                horse_read(
                    row,
                    db,
                    relation_note="Эх нь мэдэгдэхгүй" if not row.mother_id else None,
                )
            )
        result.append(
            {
                "group": HorseGroupRead.model_validate(group).model_dump(),
                "horses": [item.model_dump() for item in ordered],
            }
        )
    return result


@router.get("", response_model=list[HorseRead])
def list_horses(
    status_filter: str = "ACTIVE",
    group_id: str | None = None,
    search: str | None = None,
    _: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> list[HorseRead]:
    query = select(Horse)
    if status_filter == "ACTIVE":
        query = query.where(Horse.current_status.in_(LIVING_HORSE_STATUSES))
    elif status_filter == "ARCHIVED":
        query = query.where(Horse.current_status.in_(("ARCHIVED", "DECEASED")))
    elif status_filter != "ALL":
        raise HTTPException(status_code=400, detail="Төлөв шүүлт буруу")
    if group_id:
        query = query.where(Horse.group_id == group_id)
    if search:
        query = query.where(Horse.color.ilike(f"%{search.strip()}%"))
    return [
        horse_read(row, db)
        for row in db.scalars(query.order_by(Horse.birth_year, Horse.color)).all()
    ]


@router.post("", response_model=HorseRead)
def create_horse(
    payload: HorseCreate,
    request: Request,
    user: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> HorseRead | dict[str, Any]:
    payload_data = payload.model_dump()
    key, cached = replay(db, user, request, payload_data)
    if cached is not None:
        return cached
    validate_birth_year(payload.birth_year)
    validate_horse_links(
        db,
        group_id=payload.group_id,
        birth_year=payload.birth_year,
        mother_id=payload.mother_id,
        father_id=payload.father_id,
    )
    row = Horse(**payload_data, created_by=user.id, updated_by=user.id)
    db.add(row)
    db.flush()
    db.add(
        HorseGroupTransfer(
            horse_id=row.id,
            from_group_id=None,
            to_group_id=row.group_id,
            reason="Анхны бүртгэл",
            changed_by=user.id,
            changed_by_name=user.username,
        )
    )
    write_audit(
        db,
        user,
        "CREATE",
        request=request,
        module=MODULE_HORSES,
        entity_type="horse",
        entity_id=row.id,
        new_data=model_snapshot(row),
    )
    result = horse_read(row, db).model_dump()
    remember(db, user, request, key, payload_data, result)
    db.commit()
    return HorseRead.model_validate(result)


@router.get("/{horse_id}", response_model=HorseRead)
def get_horse(
    horse_id: str, _: AuthUser = Depends(horse_access), db: Session = Depends(get_db)
) -> HorseRead:
    row = db.get(Horse, horse_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Адуу олдсонгүй")
    return horse_read(row, db)


@router.patch("/{horse_id}", response_model=HorseRead)
def update_horse(
    horse_id: str,
    payload: HorseUpdate,
    request: Request,
    user: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> HorseRead:
    row = db.get(Horse, horse_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Адуу олдсонгүй")
    if row.current_status not in LIVING_HORSE_STATUSES:
        raise HTTPException(status_code=409, detail="Архивын адууг эхлээд сэргээнэ үү")
    require_version(row, payload.expected_version)
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    state = {
        field: changes.get(field, getattr(row, field))
        for field in (
            "color",
            "birth_year",
            "sex",
            "male_status",
            "current_status",
            "mother_id",
            "father_id",
            "additional_info",
        )
    }
    if state["sex"] == "FEMALE" and state["male_status"] is not None:
        raise HTTPException(
            status_code=400, detail="Эм адуунд эр адууны ангилал сонгохгүй"
        )
    if state["sex"] == "MALE" and state["current_status"] == "PREGNANT":
        raise HTTPException(
            status_code=400, detail="Зөвхөн эм адуу хээлтэй төлөвтэй байна"
        )
    validate_birth_year(state["birth_year"])
    validate_horse_links(
        db,
        group_id=row.group_id,
        birth_year=state["birth_year"],
        mother_id=state["mother_id"],
        father_id=state["father_id"],
        horse_id=row.id,
    )
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
        module=MODULE_HORSES,
        entity_type="horse",
        entity_id=row.id,
        previous_data=before,
        new_data=model_snapshot(row),
    )
    db.commit()
    return horse_read(row, db)


@router.post("/{horse_id}/transfer", response_model=HorseRead)
def transfer_horse(
    horse_id: str,
    payload: HorseTransferRequest,
    request: Request,
    user: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> HorseRead:
    row = db.get(Horse, horse_id)
    group = db.get(HorseGroup, payload.to_group_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Адуу олдсонгүй")
    if group is None or not group.is_active:
        raise HTTPException(status_code=404, detail="Шинэ идэвхтэй бүлэг олдсонгүй")
    if row.current_status not in LIVING_HORSE_STATUSES:
        raise HTTPException(status_code=409, detail="Архивын адууг шилжүүлэх боломжгүй")
    require_version(row, payload.expected_version)
    if row.group_id == payload.to_group_id:
        raise HTTPException(status_code=400, detail="Адуу аль хэдийн энэ бүлэгт байна")
    before = row.group_id
    row.group_id = payload.to_group_id
    row.updated_by = user.id
    row.version += 1
    db.add(
        HorseGroupTransfer(
            horse_id=row.id,
            from_group_id=before,
            to_group_id=row.group_id,
            reason=payload.reason,
            changed_by=user.id,
            changed_by_name=user.username,
        )
    )
    write_audit(
        db,
        user,
        "TRANSFER",
        request=request,
        module=MODULE_HORSES,
        entity_type="horse",
        entity_id=row.id,
        previous_data={"group_id": before},
        new_data={"group_id": row.group_id},
        detail=payload.reason,
    )
    db.commit()
    return horse_read(row, db)


@router.get("/{horse_id}/transfers", response_model=list[HorseTransferRead])
def transfer_history(
    horse_id: str, _: AuthUser = Depends(horse_access), db: Session = Depends(get_db)
) -> list[HorseTransferRead]:
    if db.get(Horse, horse_id) is None:
        raise HTTPException(status_code=404, detail="Адуу олдсонгүй")
    rows = db.scalars(
        select(HorseGroupTransfer)
        .where(HorseGroupTransfer.horse_id == horse_id)
        .order_by(HorseGroupTransfer.changed_at.desc(), HorseGroupTransfer.id.desc())
    ).all()
    result = []
    for row in rows:
        from_group = (
            db.get(HorseGroup, row.from_group_id) if row.from_group_id else None
        )
        to_group = db.get(HorseGroup, row.to_group_id)
        result.append(
            HorseTransferRead(
                id=row.id,
                horse_id=row.horse_id,
                from_group_id=row.from_group_id,
                from_group_name=from_group.name if from_group else None,
                to_group_id=row.to_group_id,
                to_group_name=to_group.name if to_group else "—",
                reason=row.reason,
                changed_by=row.changed_by,
                changed_by_name=row.changed_by_name,
                changed_at=row.changed_at,
            )
        )
    return result


@router.post("/{horse_id}/archive", response_model=HorseRead)
def archive_horse(
    horse_id: str,
    payload: ArchiveRequest,
    request: Request,
    user: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> HorseRead:
    row = db.get(Horse, horse_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Адуу олдсонгүй")
    if row.current_status not in LIVING_HORSE_STATUSES:
        raise HTTPException(status_code=409, detail="Адуу аль хэдийн архивлагдсан")
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
        module=MODULE_HORSES,
        entity_type="horse",
        entity_id=row.id,
        previous_data=before,
        new_data=model_snapshot(row),
        detail=payload.archive_note,
    )
    db.commit()
    return horse_read(row, db)


@router.post("/{horse_id}/restore", response_model=HorseRead)
def restore_horse(
    horse_id: str,
    payload: RestoreRequest,
    request: Request,
    user: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> HorseRead:
    row = db.get(Horse, horse_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Адуу олдсонгүй")
    if row.current_status not in {"ARCHIVED", "DECEASED"}:
        raise HTTPException(status_code=409, detail="Адуу архивт байхгүй")
    group = db.get(HorseGroup, row.group_id)
    if group is None or not group.is_active:
        raise HTTPException(
            status_code=409,
            detail="Адууны бүлэг идэвхгүй тул эхлээд бүлгийг сэргээнэ үү",
        )
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
        module=MODULE_HORSES,
        entity_type="horse",
        entity_id=row.id,
        previous_data=before,
        new_data=model_snapshot(row),
        detail=payload.reason,
    )
    db.commit()
    return horse_read(row, db)


@router.delete("/{horse_id}/permanent")
def permanently_delete_horse(
    horse_id: str,
    payload: PermanentDeleteRequest,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    row = db.get(Horse, horse_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Адуу олдсонгүй")
    if row.current_status not in {"ARCHIVED", "DECEASED"}:
        raise HTTPException(
            status_code=409, detail="Идэвхтэй адууг бүрмөсөн устгах боломжгүй"
        )

    transfers = list(
        db.scalars(
            select(HorseGroupTransfer).where(HorseGroupTransfer.horse_id == horse_id)
        ).all()
    )
    assets = owned_assets(db, "horse", horse_id)
    references = {
        asset.id: image_references(
            db, asset.id, excluding_type="horse", excluding_id=horse_id
        )
        for asset in assets
    }
    snapshot = {
        "record": model_snapshot(row),
        "transfers": [model_snapshot(transfer) for transfer in transfers],
        "images": [image_snapshot(asset) for asset in assets],
        "confirmation": payload.confirmation,
    }

    # External objects are removed before the database transaction is committed.
    # A storage failure therefore leaves the archived record intact and retryable.
    for asset in assets:
        if not references[asset.id]:
            delete_object(asset.storage_key)

    db.execute(update(Horse).where(Horse.mother_id == horse_id).values(mother_id=None))
    db.execute(update(Horse).where(Horse.father_id == horse_id).values(father_id=None))
    db.execute(
        delete(HorseGroupTransfer).where(HorseGroupTransfer.horse_id == horse_id)
    )
    row.main_image_id = None
    row.layout_image_id = None
    db.flush()
    db.delete(row)
    db.flush()
    for asset in assets:
        if references[asset.id]:
            asset.owner_type, asset.owner_id = references[asset.id][0]
        else:
            db.delete(asset)
    write_audit(
        db,
        user,
        "PERMANENT_DELETE",
        request=request,
        module=MODULE_HORSES,
        entity_type="horse",
        entity_id=horse_id,
        previous_data=snapshot,
        new_data=None,
        detail="Owner-confirmed permanent deletion",
    )
    db.commit()
    return {"status": "deleted", "entity_type": "horse", "entity_id": horse_id}


@router.post("/{horse_id}/images", response_model=HorseRead)
async def replace_images(
    horse_id: str,
    request: Request,
    files: list[UploadFile] = File(...),
    user: AuthUser = Depends(horse_access),
    db: Session = Depends(get_db),
) -> HorseRead:
    row = db.get(Horse, horse_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Адуу олдсонгүй")
    prepared = [await prepare_upload(file) for file in files]
    old_assets = list(
        db.scalars(
            select(ImageAsset).where(
                ImageAsset.owner_type == "horse", ImageAsset.owner_id == row.id
            )
        ).all()
    )
    new_assets, old_keys = create_image_set(
        db, owner_type="horse", owner_id=row.id, uploads=prepared, created_by=user.id
    )
    # ImageAsset has no ORM relationship to Horse, so flush the referenced rows
    # before assigning their foreign keys (required by SQLite and PostgreSQL).
    db.flush()
    main = next(asset for asset in new_assets if asset.kind == "MAIN")
    layout = next(asset for asset in new_assets if asset.kind == "LAYOUT")
    row.main_image_id = main.id
    row.layout_image_id = layout.id
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
        module=MODULE_HORSES,
        entity_type="horse",
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
            # The database points only at the committed new set. A failed cleanup
            # leaves an orphan object, never a missing current image.
            logger.warning("orphan image cleanup failed key=%s error=%s", key, exc)
    return horse_read(row, db)
