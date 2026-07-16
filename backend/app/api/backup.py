from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import MODULE_BACKUP, AuthUser, require_owner
from ..database import get_db
from ..services.backup import (
    build_backup,
    parse_backup,
    pre_restore_key,
    restore_database,
)
from ..services.storage import restore_object


router = APIRouter(prefix="/api/v1/backup", tags=["backup"])


def record_restore_failure(
    db: Session, user: AuthUser, request: Request, detail: str
) -> None:
    db.rollback()
    write_audit(
        db,
        user,
        "RESTORE_ATTEMPT",
        request=request,
        module=MODULE_BACKUP,
        entity_type="backup",
        detail=detail,
        success=False,
    )
    write_audit(
        db,
        user,
        "RESTORE_FAILED",
        request=request,
        module=MODULE_BACKUP,
        entity_type="backup",
        detail=detail,
        success=False,
    )
    db.commit()


@router.get("")
def create_backup(
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
):
    write_audit(
        db,
        user,
        "BACKUP_CREATE",
        request=request,
        module=MODULE_BACKUP,
        entity_type="backup",
    )
    db.flush()
    content = build_backup(db)
    db.commit()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=mal-toollogo-backup-v2.zip"
        },
    )


@router.post("/restore")
async def restore_backup(
    request: Request,
    confirmation: str = Form(...),
    file: UploadFile = File(...),
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if confirmation != "RESTORE":
        raise HTTPException(status_code=400, detail="Сэргээх баталгаажуулалт буруу")
    raw = await file.read()
    try:
        parsed, objects = parse_backup(raw, user.id)
        pre_backup = build_backup(db)
        restore_object(pre_backup, pre_restore_key(), "application/zip")
        for item, content in objects:
            restore_object(
                content, item["storage_key"], item.get("content_type", "image/webp")
            )
        restore_database(db, parsed)
        write_audit(
            db,
            user,
            "RESTORE_ATTEMPT",
            request=request,
            module=MODULE_BACKUP,
            entity_type="backup",
            detail=file.filename,
        )
        write_audit(
            db,
            user,
            "RESTORE_SUCCESS",
            request=request,
            module=MODULE_BACKUP,
            entity_type="backup",
            detail=file.filename,
        )
        db.commit()
    except HTTPException as exc:
        record_restore_failure(db, user, request, str(exc.detail))
        raise
    except (IntegrityError, ValueError, TypeError) as exc:
        record_restore_failure(
            db, user, request, "Backup data integrity validation failed"
        )
        raise HTTPException(
            status_code=400, detail="Backup өгөгдлийн бүрэн бүтэн байдал буруу"
        ) from exc
    return {"status": "restored", "reauthentication_required": "true"}
