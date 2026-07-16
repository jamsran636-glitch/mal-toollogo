from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Cattle, Horse, ImageAsset
from .domain import model_snapshot


def image_snapshot(asset: ImageAsset) -> dict[str, object]:
    return model_snapshot(asset)


def image_references(
    db: Session,
    asset_id: str,
    *,
    excluding_type: str,
    excluding_id: str,
) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    horse_query = select(Horse).where(
        or_(Horse.main_image_id == asset_id, Horse.layout_image_id == asset_id)
    )
    if excluding_type == "horse":
        horse_query = horse_query.where(Horse.id != excluding_id)
    horses = db.scalars(horse_query).all()
    references.extend(("horse", row.id) for row in horses)
    cattle_query = select(Cattle).where(
        or_(Cattle.main_image_id == asset_id, Cattle.layout_image_id == asset_id)
    )
    if excluding_type == "cattle":
        cattle_query = cattle_query.where(Cattle.id != excluding_id)
    cattle = db.scalars(cattle_query).all()
    references.extend(("cattle", row.id) for row in cattle)
    return references


def owned_assets(db: Session, owner_type: str, owner_id: str) -> list[ImageAsset]:
    return list(
        db.scalars(
            select(ImageAsset).where(
                ImageAsset.owner_type == owner_type,
                ImageAsset.owner_id == owner_id,
            )
        ).all()
    )
