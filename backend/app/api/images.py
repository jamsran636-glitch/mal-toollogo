from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi import Depends

from ..config import get_settings
from ..database import get_db
from ..models import ImageAsset
from ..services.storage import create_supabase_signed_url, verify_image_signature


router = APIRouter(prefix="/api/v1/images", tags=["images"])
settings = get_settings()


@router.get("/{asset_id}/content")
def image_content(
    asset_id: str, expires: int, signature: str, db: Session = Depends(get_db)
):
    if not verify_image_signature(asset_id, expires, signature):
        raise HTTPException(
            status_code=403, detail="Зургийн холбоос хүчингүй эсвэл хугацаа дууссан"
        )
    asset = db.get(ImageAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Зураг олдсонгүй")
    if settings.supabase_url and settings.supabase_service_role_key:
        return RedirectResponse(
            create_supabase_signed_url(asset.storage_key), status_code=307
        )
    if settings.is_production:
        raise HTTPException(
            status_code=503, detail="Production image storage is unavailable"
        )
    path = (settings.upload_path / asset.storage_key).resolve()
    if not path.is_relative_to(settings.upload_path) or not path.is_file():
        raise HTTPException(status_code=404, detail="Зургийн файл олдсонгүй")
    return FileResponse(path, media_type=asset.content_type)
