from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
from io import BytesIO
from pathlib import Path
import time
import uuid

import httpx
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ImageAsset


settings = get_settings()
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


@dataclass
class PreparedImage:
    image: Image.Image
    original_filename: str
    content_type: str


async def prepare_upload(upload: UploadFile) -> PreparedImage:
    raw = await upload.read(settings.max_image_bytes + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="Хоосон зураг байна")
    if len(raw) > settings.max_image_bytes:
        raise HTTPException(
            status_code=413, detail="Нэг зураг 10 MB-аас их байж болохгүй"
        )
    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415, detail="JPEG, PNG, WebP эсвэл HEIC зураг оруулна уу"
        )
    try:
        with Image.open(BytesIO(raw)) as opened:
            opened.verify()
        with Image.open(BytesIO(raw)) as opened:
            width, height = opened.size
            if width <= 0 or height <= 0 or width * height > settings.max_image_pixels:
                raise HTTPException(
                    status_code=413, detail="Зургийн пикселийн хэмжээ хэт их байна"
                )
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise HTTPException(
            status_code=400, detail="Зургийн файл гэмтсэн эсвэл дэмжигдэхгүй байна"
        ) from exc
    return PreparedImage(
        image=image,
        original_filename=Path(upload.filename or "image").name[:255],
        content_type=content_type,
    )


def encode_webp(image: Image.Image, quality: int = 85) -> bytes:
    buffer = BytesIO()
    image.save(buffer, "WEBP", quality=quality, method=6)
    return buffer.getvalue()


def supabase_headers(content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def check_storage_ready() -> None:
    """Verify the configured private bucket exists without writing an object."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=503, detail="Image storage is not configured")
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/bucket/{settings.supabase_storage_bucket}"
    try:
        response = httpx.get(url, headers=supabase_headers(), timeout=15)
        response.raise_for_status()
        bucket = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="Image storage is not ready"
        ) from exc
    if bucket.get("public") is not False:
        raise HTTPException(
            status_code=503, detail="Production image bucket must be private"
        )


def save_object(
    data: bytes, storage_key: str, content_type: str = "image/webp"
) -> None:
    if settings.supabase_url and settings.supabase_service_role_key:
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}/{storage_key}"
        try:
            response = httpx.post(
                url,
                content=data,
                headers={**supabase_headers(content_type), "x-upsert": "false"},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail="Supabase зураг хадгалах үйлчилгээ амжилтгүй"
            ) from exc
        return
    if settings.is_production:
        raise HTTPException(
            status_code=503, detail="Production image storage is not configured"
        )
    path = settings.upload_path / storage_key
    if not path.resolve().is_relative_to(settings.upload_path):
        raise HTTPException(status_code=400, detail="Зургийн хадгалах зам буруу")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def restore_object(
    data: bytes, storage_key: str, content_type: str = "image/webp"
) -> None:
    if settings.supabase_url and settings.supabase_service_role_key:
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}/{storage_key}"
        try:
            response = httpx.post(
                url,
                content=data,
                headers={**supabase_headers(content_type), "x-upsert": "true"},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail="Backup зураг сэргээх үйлчилгээ амжилтгүй"
            ) from exc
        return
    if settings.is_production:
        raise HTTPException(
            status_code=503, detail="Production image storage is not configured"
        )
    path = (settings.upload_path / storage_key).resolve()
    if not path.is_relative_to(settings.upload_path):
        raise HTTPException(status_code=400, detail="Backup зургийн зам буруу")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_object(storage_key: str) -> bytes:
    if settings.supabase_url and settings.supabase_service_role_key:
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/authenticated/{settings.supabase_storage_bucket}/{storage_key}"
        try:
            response = httpx.get(url, headers=supabase_headers(), timeout=30)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail="Backup-д оруулах зураг татаж чадсангүй"
            ) from exc
    if settings.is_production:
        raise HTTPException(
            status_code=503, detail="Production image storage is not configured"
        )
    path = (settings.upload_path / storage_key).resolve()
    if not path.is_relative_to(settings.upload_path) or not path.is_file():
        raise HTTPException(
            status_code=409, detail=f"Зургийн файл олдсонгүй: {storage_key}"
        )
    return path.read_bytes()


def delete_object(storage_key: str) -> None:
    if settings.supabase_url and settings.supabase_service_role_key:
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}/{storage_key}"
        response = httpx.delete(url, headers=supabase_headers(), timeout=30)
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
        return
    if settings.is_production:
        raise HTTPException(
            status_code=503, detail="Production image storage is not configured"
        )
    path = (settings.upload_path / storage_key).resolve()
    if path.is_relative_to(settings.upload_path) and path.is_file():
        path.unlink()


def add_asset(
    db: Session,
    *,
    owner_type: str,
    owner_id: str,
    kind: str,
    image: Image.Image,
    filename: str,
    created_by: str,
    quality: int = 85,
) -> ImageAsset:
    data = encode_webp(image, quality)
    asset_id = str(uuid.uuid4())
    storage_key = f"{owner_type}/{owner_id}/{asset_id}.webp"
    save_object(data, storage_key)
    row = ImageAsset(
        id=asset_id,
        owner_type=owner_type,
        owner_id=owner_id,
        kind=kind,
        storage_key=storage_key,
        original_filename=filename,
        content_type="image/webp",
        size_bytes=len(data),
        width=image.width,
        height=image.height,
        checksum_sha256=sha256(data).hexdigest(),
        created_by=created_by,
    )
    db.add(row)
    return row


def create_image_set(
    db: Session,
    *,
    owner_type: str,
    owner_id: str,
    uploads: list[PreparedImage],
    created_by: str,
) -> tuple[list[ImageAsset], list[str]]:
    if not uploads or len(uploads) > 8:
        raise HTTPException(status_code=400, detail="1-8 зураг сонгоно уу")
    old_assets = list(
        db.scalars(
            select(ImageAsset).where(
                ImageAsset.owner_type == owner_type, ImageAsset.owner_id == owner_id
            )
        ).all()
    )
    new_assets: list[ImageAsset] = []
    try:
        for upload in uploads:
            new_assets.append(
                add_asset(
                    db,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    kind="DETAIL",
                    image=upload.image,
                    filename=upload.original_filename,
                    created_by=created_by,
                )
            )
        new_assets.append(
            add_asset(
                db,
                owner_type=owner_type,
                owner_id=owner_id,
                kind="MAIN",
                image=uploads[0].image,
                filename=uploads[0].original_filename,
                created_by=created_by,
            )
        )
        cell = 600
        rows = (len(uploads) + 1) // 2
        layout = Image.new("RGB", (cell * 2, cell * rows), (245, 244, 238))
        for index, upload in enumerate(uploads):
            fitted = ImageOps.fit(
                upload.image, (cell, cell), method=Image.Resampling.LANCZOS
            )
            layout.paste(fitted, ((index % 2) * cell, (index // 2) * cell))
        new_assets.append(
            add_asset(
                db,
                owner_type=owner_type,
                owner_id=owner_id,
                kind="LAYOUT",
                image=layout,
                filename="combined-layout.webp",
                created_by=created_by,
                quality=82,
            )
        )
    except Exception:
        for asset in new_assets:
            try:
                delete_object(asset.storage_key)
            except httpx.HTTPError:
                pass
        raise
    old_keys = [asset.storage_key for asset in old_assets]
    return new_assets, old_keys


def signed_proxy_url(asset_id: str, expires_in: int = 900) -> str:
    expires = int(time.time()) + expires_in
    message = f"{asset_id}:{expires}".encode()
    signature = hmac.new(settings.jwt_secret.encode(), message, sha256).hexdigest()
    return f"/api/v1/images/{asset_id}/content?expires={expires}&signature={signature}"


def verify_image_signature(asset_id: str, expires: int, signature: str) -> bool:
    if expires < int(time.time()):
        return False
    expected = hmac.new(
        settings.jwt_secret.encode(), f"{asset_id}:{expires}".encode(), sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_supabase_signed_url(storage_key: str, expires_in: int = 900) -> str:
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/{settings.supabase_storage_bucket}/{storage_key}"
    try:
        response = httpx.post(
            url,
            json={"expiresIn": expires_in},
            headers=supabase_headers("application/json"),
            timeout=15,
        )
        response.raise_for_status()
        signed = response.json().get("signedURL")
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail="Зургийн түр холбоос үүсгэсэнгүй"
        ) from exc
    if not isinstance(signed, str):
        raise HTTPException(status_code=502, detail="Зургийн түр холбоос буруу байна")
    return (
        signed
        if signed.startswith("http")
        else f"{settings.supabase_url.rstrip('/')}/storage/v1{signed}"
    )
