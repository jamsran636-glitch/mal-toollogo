from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..services.storage import check_storage_ready


router = APIRouter(tags=["system"])
settings = get_settings()


@router.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running", "version": "2.0.0"}


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        revision = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Database or schema is not ready"
        ) from exc
    return {"status": "ready", "database": "ok", "migration": str(revision)}


@router.get("/ready/storage")
def storage_ready() -> dict[str, str]:
    check_storage_ready()
    return {"status": "ready", "storage": "ok", "bucket_policy": "private"}
