from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import uuid
import zipfile

from fastapi import HTTPException
from sqlalchemy import Date, DateTime, inspect as sa_inspect, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    AuditLog,
    Cattle,
    DashboardPreference,
    FinanceEntry,
    Herder,
    Horse,
    HorseGroup,
    HorseGroupTransfer,
    ImageAsset,
    IdempotencyRecord,
    InventorySnapshot,
    SmallLivestockCount,
    SmallLivestockLoss,
    User,
    UserSession,
    LoginAttempt,
)
from .domain import model_snapshot
from .storage import read_object


settings = get_settings()
BACKUP_MODELS = (
    User,
    AuditLog,
    HorseGroup,
    ImageAsset,
    Horse,
    HorseGroupTransfer,
    Cattle,
    SmallLivestockCount,
    Herder,
    SmallLivestockLoss,
    FinanceEntry,
    InventorySnapshot,
    DashboardPreference,
)
MODEL_BY_TABLE = {model.__tablename__: model for model in BACKUP_MODELS}
MANDATORY_TABLES = frozenset(MODEL_BY_TABLE)


def json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Unsupported backup value: {type(value).__name__}")


def safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > 10_000:
        raise HTTPException(status_code=413, detail="Backup дотор хэт олон файл байна")
    expanded = sum(member.file_size for member in members)
    if expanded > settings.max_backup_expanded_bytes:
        raise HTTPException(
            status_code=413, detail="Backup задлагдсан хэмжээ хэт их байна"
        )
    for member in members:
        path = Path(member.filename)
        if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
            raise HTTPException(
                status_code=400, detail="Backup дотор зөвшөөрөгдөөгүй зам байна"
            )
    return members


def build_backup(db: Session) -> bytes:
    data = {
        model.__tablename__: [
            model_snapshot(row) for row in db.scalars(select(model)).all()
        ]
        for model in BACKUP_MODELS
    }
    data_bytes = json.dumps(
        data, ensure_ascii=False, default=json_default, sort_keys=True
    ).encode("utf-8")
    assets = list(db.scalars(select(ImageAsset)).all())
    object_payloads: list[tuple[ImageAsset, bytes]] = []
    object_manifest = []
    for asset in assets:
        raw = read_object(asset.storage_key)
        checksum = sha256(raw).hexdigest()
        if checksum != asset.checksum_sha256:
            raise HTTPException(
                status_code=409,
                detail=f"Зургийн checksum зөрүүтэй: {asset.storage_key}",
            )
        object_payloads.append((asset, raw))
        object_manifest.append(
            {
                "storage_key": asset.storage_key,
                "archive_path": f"objects/{asset.storage_key}",
                "size": len(raw),
                "sha256": checksum,
                "content_type": asset.content_type,
            }
        )
    manifest = {
        "schema_version": settings.backup_schema_version,
        "application": "mal-toollogo",
        "application_version": "2.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": sorted(MANDATORY_TABLES),
        "data_sha256": sha256(data_bytes).hexdigest(),
        "objects": object_manifest,
        "warning": "This archive contains sensitive family, authentication-hash, and registration data. Store securely.",
    }
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
        archive.writestr("data.json", data_bytes)
        for asset, raw in object_payloads:
            archive.writestr(f"objects/{asset.storage_key}", raw)
    return output.getvalue()


def parse_value(column, value):
    if value is None:
        return None
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return datetime.fromisoformat(value)
    if (
        isinstance(column.type, Date)
        and not isinstance(column.type, DateTime)
        and isinstance(value, str)
    ):
        return date.fromisoformat(value)
    return value


def validate_rows(data: dict, current_owner_id: str) -> dict[str, list[dict]]:
    if set(data) != MANDATORY_TABLES:
        missing = sorted(MANDATORY_TABLES - set(data))
        extra = sorted(set(data) - MANDATORY_TABLES)
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Backup хүснэгт дутуу эсвэл илүү",
                "missing": missing,
                "extra": extra,
            },
        )
    parsed: dict[str, list[dict]] = {}
    for table, model in MODEL_BY_TABLE.items():
        rows = data[table]
        if not isinstance(rows, list):
            raise HTTPException(
                status_code=400, detail=f"{table} хүснэгтийн өгөгдөл жагсаалт биш"
            )
        columns = {column.key: column for column in sa_inspect(model).columns}
        table_rows = []
        seen_primary_keys = set()
        primary_keys = [column.key for column in sa_inspect(model).primary_key]
        for original in rows:
            if not isinstance(original, dict) or set(original) != set(columns):
                raise HTTPException(
                    status_code=400, detail=f"{table} мөрийн багана тохирохгүй"
                )
            item = {
                key: parse_value(columns[key], value) for key, value in original.items()
            }
            key = tuple(item[name] for name in primary_keys)
            if key in seen_primary_keys:
                raise HTTPException(
                    status_code=400, detail=f"{table} давхардсан primary key"
                )
            seen_primary_keys.add(key)
            table_rows.append(item)
        parsed[table] = table_rows

    users = {row["id"]: row for row in parsed["users"]}
    owner = users.get(current_owner_id)
    if owner is None or owner["role"] != "OWNER" or not owner["is_active"]:
        raise HTTPException(
            status_code=400,
            detail="Backup нь одоогийн идэвхтэй эзэмшигчийн бүртгэлийг агуулаагүй",
        )
    if any(
        not str(row["password_hash"]).startswith("$argon2") for row in parsed["users"]
    ):
        raise HTTPException(
            status_code=400, detail="Backup дотор зөвшөөрөгдөөгүй credential hash байна"
        )

    user_ids = set(users)
    group_ids = {row["id"] for row in parsed["horse_groups"]}
    image_ids = {row["id"] for row in parsed["image_assets"]}
    horse_ids = {row["id"] for row in parsed["horses"]}
    cattle_ids = {row["id"] for row in parsed["cattle"]}
    herder_ids = {row["id"] for row in parsed["herders"]}
    for table in (
        "horse_groups",
        "horses",
        "cattle",
        "small_livestock_counts",
        "small_livestock_losses",
        "finance_entries",
        "herders",
    ):
        for row in parsed[table]:
            for field in ("created_by", "updated_by"):
                if field in row and row[field] not in user_ids:
                    raise HTTPException(
                        status_code=400, detail=f"{table}.{field} хэрэглэгч олдсонгүй"
                    )
    for row in parsed["image_assets"]:
        if row["created_by"] not in user_ids:
            raise HTTPException(
                status_code=400, detail="image_assets.created_by хэрэглэгч олдсонгүй"
            )
    for row in parsed["horses"]:
        if (
            row["group_id"] not in group_ids
            or (row["mother_id"] and row["mother_id"] not in horse_ids)
            or (row["father_id"] and row["father_id"] not in horse_ids)
        ):
            raise HTTPException(
                status_code=400, detail="Адууны бүлэг/эцэг/эх холбоос буруу"
            )
        if (row["main_image_id"] and row["main_image_id"] not in image_ids) or (
            row["layout_image_id"] and row["layout_image_id"] not in image_ids
        ):
            raise HTTPException(status_code=400, detail="Адууны зураг холбоос буруу")
    for row in parsed["cattle"]:
        if row["mother_id"] and row["mother_id"] not in cattle_ids:
            raise HTTPException(status_code=400, detail="Үхрийн эхийн холбоос буруу")
        if (row["main_image_id"] and row["main_image_id"] not in image_ids) or (
            row["layout_image_id"] and row["layout_image_id"] not in image_ids
        ):
            raise HTTPException(status_code=400, detail="Үхрийн зураг холбоос буруу")
    for row in parsed["small_livestock_losses"]:
        if row["herder_id"] and row["herder_id"] not in herder_ids:
            raise HTTPException(
                status_code=400, detail="Хорогдлын малчин холбоос буруу"
            )
    return parsed


def parse_backup(
    raw: bytes, current_owner_id: str
) -> tuple[dict[str, list[dict]], list[tuple[dict, bytes]]]:
    if not raw or len(raw) > settings.max_backup_bytes:
        raise HTTPException(
            status_code=413, detail="Backup файл хоосон эсвэл 50 MB-аас их байна"
        )
    try:
        archive = zipfile.ZipFile(BytesIO(raw))
        members = safe_members(archive)
        names = {member.filename for member in members}
        if not {"manifest.json", "data.json"}.issubset(names):
            raise HTTPException(
                status_code=400, detail="Backup manifest.json эсвэл data.json дутуу"
            )
        manifest = json.loads(archive.read("manifest.json"))
        data_bytes = archive.read("data.json")
        data = json.loads(data_bytes)
    except HTTPException:
        raise
    except (
        zipfile.BadZipFile,
        json.JSONDecodeError,
        KeyError,
        UnicodeDecodeError,
    ) as exc:
        raise HTTPException(
            status_code=400, detail="Backup файл хүчингүй байна"
        ) from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != settings.backup_schema_version
    ):
        raise HTTPException(
            status_code=400, detail="Backup schema version дэмжигдэхгүй"
        )
    if (
        manifest.get("application") != "mal-toollogo"
        or set(manifest.get("tables", [])) != MANDATORY_TABLES
    ):
        raise HTTPException(status_code=400, detail="Backup manifest тохирохгүй")
    if manifest.get("data_sha256") != sha256(data_bytes).hexdigest():
        raise HTTPException(status_code=400, detail="Backup data checksum зөрүүтэй")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Backup data object биш")
    parsed = validate_rows(data, current_owner_id)
    objects = manifest.get("objects")
    if not isinstance(objects, list):
        raise HTTPException(status_code=400, detail="Backup object manifest буруу")
    expected_keys = {row["storage_key"] for row in parsed["image_assets"]}
    manifest_keys = {
        item.get("storage_key") for item in objects if isinstance(item, dict)
    }
    if manifest_keys != expected_keys:
        raise HTTPException(status_code=400, detail="Backup зураг manifest бүрэн биш")
    object_payloads: list[tuple[dict, bytes]] = []
    for item in objects:
        path = item.get("archive_path")
        if (
            not isinstance(path, str)
            or path not in names
            or not path.startswith("objects/")
        ):
            raise HTTPException(status_code=400, detail="Backup зураг файл дутуу")
        content = archive.read(path)
        if len(content) != item.get("size") or sha256(content).hexdigest() != item.get(
            "sha256"
        ):
            raise HTTPException(
                status_code=400, detail="Backup зураг checksum зөрүүтэй"
            )
        object_payloads.append((item, content))
    return parsed, object_payloads


def topological_rows(rows: list[dict], parent_fields: tuple[str, ...]) -> list[dict]:
    pending = {row["id"]: row for row in rows}
    ordered: list[dict] = []
    while pending:
        ready = [
            row
            for row in pending.values()
            if all(
                not row[field] or row[field] not in pending for field in parent_fields
            )
        ]
        if not ready:
            raise HTTPException(
                status_code=400, detail="Backup дотор удам угсааны тойрог холбоос байна"
            )
        for row in ready:
            ordered.append(row)
            pending.pop(row["id"])
    return ordered


def restore_database(db: Session, parsed: dict[str, list[dict]]) -> None:
    deletion_order = (
        IdempotencyRecord,
        UserSession,
        LoginAttempt,
        AuditLog,
        HorseGroupTransfer,
        Horse,
        Cattle,
        SmallLivestockLoss,
        SmallLivestockCount,
        FinanceEntry,
        InventorySnapshot,
        DashboardPreference,
        Herder,
        HorseGroup,
        ImageAsset,
        User,
    )
    for model in deletion_order:
        db.query(model).delete(synchronize_session=False)
    db.flush()

    insertion_order: list[tuple[type, list[dict]]] = [
        (User, parsed["users"]),
        (ImageAsset, parsed["image_assets"]),
        (HorseGroup, parsed["horse_groups"]),
        (Herder, parsed["herders"]),
        (FinanceEntry, parsed["finance_entries"]),
        (SmallLivestockCount, parsed["small_livestock_counts"]),
        (InventorySnapshot, parsed["inventory_snapshots"]),
        (DashboardPreference, parsed["dashboard_preferences"]),
        (Horse, topological_rows(parsed["horses"], ("mother_id", "father_id"))),
        (Cattle, topological_rows(parsed["cattle"], ("mother_id",))),
        (HorseGroupTransfer, parsed["horse_group_transfers"]),
        (SmallLivestockLoss, parsed["small_livestock_losses"]),
        (AuditLog, parsed["audit_logs"]),
    ]
    for model, rows in insertion_order:
        for row in rows:
            db.add(model(**row))
        db.flush()
    if db.bind and db.bind.dialect.name == "postgresql":
        for table in ("audit_logs", "horse_group_transfers"):
            db.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1), true)"
                )
            )


def pre_restore_key() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"backups/pre-restore-{stamp}-{uuid.uuid4().hex}.zip"
