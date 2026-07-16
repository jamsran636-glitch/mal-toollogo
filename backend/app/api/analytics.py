from datetime import date, datetime
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import MODULE_ANALYTICS, AuthUser, require_module, require_owner
from ..database import get_db
from ..models import (
    Cattle,
    DashboardPreference,
    FinanceEntry,
    Horse,
    InventorySnapshot,
    SmallLivestockCount,
    SmallLivestockLoss,
)
from ..schemas import DashboardPreferenceUpdate, SnapshotCreate
from ..services.domain import (
    LIVING_HORSE_STATUSES,
    age_years,
    cattle_age_category,
    horse_age_category,
    model_snapshot,
    small_count_dict,
)


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
analytics_access = require_module(MODULE_ANALYTICS)
DEFAULT_WIDGETS = [
    "profit",
    "counts",
    "mortality",
    "growth",
    "expenses",
    "adult_males",
    "balance",
]


@router.get("/access")
def access(user: AuthUser = Depends(analytics_access)) -> dict[str, str]:
    return {"status": "allowed", "module": MODULE_ANALYTICS, "username": user.username}


@router.get("/snapshots")
def list_snapshots(
    _: AuthUser = Depends(require_owner), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(InventorySnapshot).order_by(
            InventorySnapshot.snapshot_date, InventorySnapshot.module
        )
    ).all()
    return [model_snapshot(row) for row in rows]


@router.post("/snapshots")
def create_snapshot(
    payload: SnapshotCreate,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    existing = db.scalar(
        select(InventorySnapshot).where(
            InventorySnapshot.module == payload.module,
            InventorySnapshot.snapshot_date == payload.snapshot_date,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Энэ модуль, огнооны үлдэгдэл бүртгэлтэй байна"
        )
    row = InventorySnapshot(**payload.model_dump(), source="MANUAL", created_by=user.id)
    db.add(row)
    db.flush()
    result = model_snapshot(row)
    write_audit(
        db,
        user,
        "CREATE",
        request=request,
        module=MODULE_ANALYTICS,
        entity_type="inventory_snapshot",
        entity_id=row.id,
        new_data=result,
        detail=payload.note,
    )
    db.commit()
    return result


@router.get("/preferences")
def get_preferences(
    user: AuthUser = Depends(require_owner), db: Session = Depends(get_db)
) -> dict[str, list[str]]:
    row = db.get(DashboardPreference, user.id)
    return {
        "visible_widgets": json.loads(row.visible_widgets) if row else DEFAULT_WIDGETS
    }


@router.put("/preferences")
def set_preferences(
    payload: DashboardPreferenceUpdate,
    request: Request,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, list[str]]:
    row = db.get(DashboardPreference, user.id)
    before = json.loads(row.visible_widgets) if row else DEFAULT_WIDGETS
    if row is None:
        row = DashboardPreference(
            user_id=user.id, visible_widgets=json.dumps(payload.visible_widgets)
        )
        db.add(row)
    else:
        row.visible_widgets = json.dumps(payload.visible_widgets)
    write_audit(
        db,
        user,
        "UPDATE",
        request=request,
        module=MODULE_ANALYTICS,
        entity_type="dashboard_preference",
        entity_id=user.id,
        previous_data=before,
        new_data=payload.visible_widgets,
    )
    db.commit()
    return {"visible_widgets": payload.visible_widgets}


@router.get("/dashboard")
def dashboard(
    year: int | None = None,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    selected_year = year or date.today().year
    if selected_year < 2000 or selected_year > date.today().year + 1:
        raise HTTPException(status_code=400, detail="Тайлангийн он буруу")

    start = date(selected_year, 1, 1)
    end = date(selected_year, 12, 31)
    finance = list(
        db.scalars(
            select(FinanceEntry).where(
                FinanceEntry.archived_at.is_(None),
                FinanceEntry.entry_date >= start,
                FinanceEntry.entry_date <= end,
            )
        ).all()
    )
    modules = ["horses", "cattle", "small_livestock", "general"]
    by_module = {module: {"income": 0, "expense": 0, "profit": 0} for module in modules}
    expense_categories: dict[str, int] = {}
    monthly = {
        month: {"income": 0, "expense": 0, "profit": 0} for month in range(1, 13)
    }
    for entry in finance:
        module = entry.livestock_module
        key = "income" if entry.entry_type == "INCOME" else "expense"
        by_module[module][key] += entry.amount
        monthly[entry.entry_date.month][key] += entry.amount
        if entry.entry_type == "EXPENSE":
            category = entry.category or "Бусад"
            expense_categories[category] = (
                expense_categories.get(category, 0) + entry.amount
            )
    for values in by_module.values():
        values["profit"] = values["income"] - values["expense"]
    for values in monthly.values():
        values["profit"] = values["income"] - values["expense"]

    horses = list(
        db.scalars(
            select(Horse).where(Horse.current_status.in_(LIVING_HORSE_STATUSES))
        ).all()
    )
    cattle = list(
        db.scalars(select(Cattle).where(Cattle.current_status == "ACTIVE")).all()
    )
    latest_count = db.scalar(
        select(SmallLivestockCount)
        .where(SmallLivestockCount.count_type == "FULL")
        .order_by(SmallLivestockCount.count_date.desc())
    )
    small = (
        small_count_dict(latest_count)
        if latest_count
        else {"total": 0, "sheep_male": 0, "goat_male": 0, "ram": 0, "buck": 0}
    )

    snapshots = list(
        db.scalars(
            select(InventorySnapshot).order_by(InventorySnapshot.snapshot_date)
        ).all()
    )
    snapshot_years = sorted({row.snapshot_date.year for row in snapshots})
    growth = []
    for snapshot_year in snapshot_years:
        values: dict[str, int | None] = {
            "horses": None,
            "cattle": None,
            "small_livestock": None,
        }
        for row in snapshots:
            if row.snapshot_date.year == snapshot_year:
                values[row.module] = row.count
        growth.append({"year": snapshot_year, **values})

    horse_deaths = list(
        db.scalars(
            select(Horse).where(
                Horse.current_status == "DECEASED",
                Horse.archived_at >= datetime(selected_year, 1, 1),
                Horse.archived_at < datetime(selected_year + 1, 1, 1),
            )
        ).all()
    )
    cattle_deaths = list(
        db.scalars(
            select(Cattle).where(
                Cattle.current_status == "DECEASED",
                Cattle.archived_at >= datetime(selected_year, 1, 1),
                Cattle.archived_at < datetime(selected_year + 1, 1, 1),
            )
        ).all()
    )
    small_losses = list(
        db.scalars(
            select(SmallLivestockLoss).where(
                SmallLivestockLoss.loss_date >= start,
                SmallLivestockLoss.loss_date <= end,
            )
        ).all()
    )
    mortality = {
        "horses": {
            "total": len(horse_deaths),
            "abnormal": sum(1 for row in horse_deaths if row.unnatural_loss),
        },
        "cattle": {
            "total": len(cattle_deaths),
            "abnormal": sum(1 for row in cattle_deaths if row.unnatural_loss),
        },
        "small_livestock": {
            "total": sum(row.quantity for row in small_losses),
            "abnormal": sum(row.quantity for row in small_losses if row.unnatural_loss),
        },
    }

    horse_age = {key: 0 for key in ["Даага", "Шүдлэн", "Хязаалан", "Соёолон", "Их нас"]}
    cattle_age = {
        key: 0 for key in ["Бяруу", "Шүдлэн", "Хязаалан", "Соёолон", "Бүдүүн эр үхэр"]
    }
    for row in horses:
        years = age_years(row.birth_year)
        if row.sex == "MALE" and row.male_status != "STALLION" and years >= 1:
            horse_age[horse_age_category(years)] += 1
    for row in cattle:
        years = age_years(row.birth_year)
        if row.sex == "MALE" and not row.is_bull and years >= 1:
            cattle_age[cattle_age_category(years, row.sex)] += 1

    preference = db.get(DashboardPreference, user.id)
    return {
        "year": selected_year,
        "visible_widgets": json.loads(preference.visible_widgets)
        if preference
        else DEFAULT_WIDGETS,
        "livestock_counts": {
            "horses": len(horses),
            "cattle": len(cattle),
            "small_livestock": small.get("total", 0),
        },
        "profit_by_livestock": by_module,
        "mortality": mortality,
        "growth": growth,
        "growth_note": "Зөвхөн баталгаажуулсан 1-р сарын 1-ний үлдэгдэл харуулна. Байхгүй утгыг null гэж тэмдэглэнэ.",
        "expense_categories": expense_categories,
        "monthly_balance": [
            {"month": month, **monthly[month]} for month in range(1, 13)
        ],
        "adult_males": {
            "horses": {"total": sum(horse_age.values()), "age_structure": horse_age},
            "cattle": {"total": sum(cattle_age.values()), "age_structure": cattle_age},
            "small_livestock": {
                "total": small.get("sheep_male", 0) + small.get("goat_male", 0),
                "structure": {
                    "Эр хонь": small.get("sheep_male", 0),
                    "Эр ямаа": small.get("goat_male", 0),
                },
            },
        },
    }
