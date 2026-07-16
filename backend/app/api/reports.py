from datetime import date, datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import MODULE_REPORTS, AuthUser, require_owner
from ..database import get_db
from ..models import (
    AuditLog,
    Cattle,
    FinanceEntry,
    Herder,
    Horse,
    HorseGroupTransfer,
    SmallLivestockCount,
    SmallLivestockLoss,
)
from ..services.domain import model_snapshot, small_count_dict


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def excel_value(value: Any) -> Any:
    """Return values openpyxl can serialize consistently across SQLite/PostgreSQL."""
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def register_font() -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            pdfmetrics.registerFont(TTFont("MongolianSans", candidate))
            return "MongolianSans"
    return "Helvetica"


def selected_rows(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    module: str | None,
    status: str | None,
    finance_year: int | None,
    finance_month: int | None,
    census_type: str | None,
    mortality_type: str | None,
) -> dict[str, list[dict[str, Any]]]:
    horses_query = select(Horse)
    cattle_query = select(Cattle)
    if status == "active":
        horses_query = horses_query.where(
            Horse.current_status.in_(("ACTIVE", "PREGNANT"))
        )
        cattle_query = cattle_query.where(Cattle.current_status == "ACTIVE")
    elif status == "archived":
        horses_query = horses_query.where(
            Horse.current_status.in_(("ARCHIVED", "DECEASED"))
        )
        cattle_query = cattle_query.where(
            Cattle.current_status.in_(("ARCHIVED", "DECEASED"))
        )

    counts_query = select(SmallLivestockCount)
    if census_type:
        counts_query = counts_query.where(SmallLivestockCount.count_type == census_type)
    if date_from:
        counts_query = counts_query.where(SmallLivestockCount.count_date >= date_from)
    if date_to:
        counts_query = counts_query.where(SmallLivestockCount.count_date <= date_to)

    losses_query = select(SmallLivestockLoss)
    if mortality_type:
        losses_query = losses_query.where(
            SmallLivestockLoss.livestock_type == mortality_type
        )
    if date_from:
        losses_query = losses_query.where(SmallLivestockLoss.loss_date >= date_from)
    if date_to:
        losses_query = losses_query.where(SmallLivestockLoss.loss_date <= date_to)

    finance_query = select(FinanceEntry)
    if finance_year:
        finance_query = finance_query.where(
            FinanceEntry.entry_date >= date(finance_year, 1, 1),
            FinanceEntry.entry_date <= date(finance_year, 12, 31),
        )
    if finance_month and finance_year:
        finance_query = finance_query.where(
            FinanceEntry.entry_date >= date(finance_year, finance_month, 1)
        )
        next_month = date(
            finance_year + (finance_month == 12),
            1 if finance_month == 12 else finance_month + 1,
            1,
        )
        finance_query = finance_query.where(FinanceEntry.entry_date < next_month)
    if module:
        finance_query = finance_query.where(FinanceEntry.livestock_module == module)

    result = {
        "Horses": [model_snapshot(row) for row in db.scalars(horses_query).all()]
        if module in {None, "horses"}
        else [],
        "Horse transfers": [
            model_snapshot(row) for row in db.scalars(select(HorseGroupTransfer)).all()
        ]
        if module in {None, "horses"}
        else [],
        "Cattle": [model_snapshot(row) for row in db.scalars(cattle_query).all()]
        if module in {None, "cattle"}
        else [],
        "Full censuses": [
            small_count_dict(row)
            for row in db.scalars(
                counts_query.where(SmallLivestockCount.count_type == "FULL")
            ).all()
        ]
        if module in {None, "small_livestock"}
        else [],
        "Evening censuses": [
            small_count_dict(row)
            for row in db.scalars(
                counts_query.where(SmallLivestockCount.count_type == "EVENING")
            ).all()
        ]
        if module in {None, "small_livestock"}
        else [],
        "Mortality": [model_snapshot(row) for row in db.scalars(losses_query).all()]
        if module in {None, "small_livestock"}
        else [],
        "Finance": [model_snapshot(row) for row in db.scalars(finance_query).all()],
        "Herders": [model_snapshot(row) for row in db.scalars(select(Herder)).all()],
        "Audit summary": [
            {
                "username": row.username,
                "role": row.role,
                "action": row.action,
                "module": row.module,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "success": row.success,
                "created_at": row.created_at,
            }
            for row in db.scalars(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1000)
            ).all()
        ],
    }
    return result


@router.get("/excel")
def excel_report(
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    module: str | None = None,
    status: str | None = None,
    finance_year: int | None = None,
    finance_month: int | None = None,
    census_type: str | None = None,
    mortality_type: str | None = None,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
):
    sheets = selected_rows(
        db,
        date_from=date_from,
        date_to=date_to,
        module=module,
        status=status,
        finance_year=finance_year,
        finance_month=finance_month,
        census_type=census_type,
        mortality_type=mortality_type,
    )
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets.items():
        sheet = workbook.create_sheet(title[:31])
        if not rows:
            sheet.append(["Мэдээлэл байхгүй"])
            continue
        columns = list(rows[0])
        sheet.append(columns)
        for row in rows:
            sheet.append([excel_value(row.get(column)) for column in columns])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    write_audit(
        db,
        user,
        "EXPORT_EXCEL",
        request=request,
        module=MODULE_REPORTS,
        entity_type="report",
        new_data={
            "filters": {
                "module": module,
                "status": status,
                "date_from": date_from,
                "date_to": date_to,
            }
        },
    )
    db.commit()
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=mal-toollogo-report.xlsx"
        },
    )


@router.get("/pdf")
def pdf_report(
    request: Request,
    year: int | None = None,
    user: AuthUser = Depends(require_owner),
    db: Session = Depends(get_db),
):
    selected_year = year or date.today().year
    horses = list(
        db.scalars(
            select(Horse).where(Horse.current_status.in_(("ACTIVE", "PREGNANT")))
        ).all()
    )
    cattle = list(
        db.scalars(select(Cattle).where(Cattle.current_status == "ACTIVE")).all()
    )
    latest = db.scalar(
        select(SmallLivestockCount)
        .where(SmallLivestockCount.count_type == "FULL")
        .order_by(SmallLivestockCount.count_date.desc())
    )
    small = small_count_dict(latest).get("total", 0) if latest else 0
    entries = list(
        db.scalars(
            select(FinanceEntry).where(
                FinanceEntry.archived_at.is_(None),
                FinanceEntry.entry_date >= date(selected_year, 1, 1),
                FinanceEntry.entry_date <= date(selected_year, 12, 31),
            )
        ).all()
    )
    income = sum(row.amount for row in entries if row.entry_type == "INCOME")
    expense = sum(row.amount for row in entries if row.entry_type == "EXPENSE")
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    font = register_font()
    pdf.setFont(font, 18)
    pdf.drawString(50, height - 60, f"Мал тооллого — {selected_year} оны товч тайлан")
    lines = [
        f"Адуу: {len(horses)}",
        f"Үхэр: {len(cattle)}",
        f"Хонь, ямаа: {small}",
        f"Орлого: {income:,} ₮",
        f"Зарлага: {expense:,} ₮",
        f"Цэвэр ашиг: {income - expense:,} ₮",
    ]
    pdf.setFont(font, 12)
    y = height - 110
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 24
    pdf.save()
    output.seek(0)
    write_audit(
        db,
        user,
        "EXPORT_PDF",
        request=request,
        module=MODULE_REPORTS,
        entity_type="report",
        new_data={"year": selected_year},
    )
    db.commit()
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=mal-toollogo-report.pdf"},
    )
