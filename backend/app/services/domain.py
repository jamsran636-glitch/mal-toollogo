from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from ..models import Cattle, Horse, HorseGroup, SmallLivestockCount


LIVING_HORSE_STATUSES = ("ACTIVE", "PREGNANT")
ACTIVE_CATTLE_STATUS = "ACTIVE"


def age_years(birth_year: int, on_date: date | None = None) -> int:
    current = on_date or date.today()
    years = current.year - birth_year
    if (current.month, current.day) < (4, 1):
        years -= 1
    return max(0, years)


def horse_age_category(years: int) -> str:
    return {0: "Унага", 1: "Даага", 2: "Шүдлэн", 3: "Хязаалан", 4: "Соёолон"}.get(
        years, "Их нас"
    )


def cattle_age_category(years: int, sex: str) -> str:
    if years == 0:
        return "Тугал"
    if years == 1:
        return "Бяруу"
    if years == 2:
        return "Шүдлэн"
    if years == 3:
        return "Хязаалан"
    if years == 4:
        return "Соёолон"
    return "Бүдүүн үнээ" if sex == "FEMALE" else "Бүдүүн эр үхэр"


def horse_label(horse: Horse) -> str:
    years = age_years(horse.birth_year)
    category = horse_age_category(years)
    if years == 0:
        suffix = "унага"
    elif horse.sex == "FEMALE":
        suffix = "гүү"
    elif horse.male_status == "STALLION":
        suffix = "азарга"
    elif years <= 4 and horse.male_status != "GELDING":
        suffix = "үрээ"
    else:
        suffix = "морь"
    return (
        f"{horse.color} {suffix}"
        if category in {"Унага", "Их нас"}
        else f"{category.lower()} {horse.color} {suffix}"
    )


def model_snapshot(row: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    excluded = exclude or set()
    return {
        column.key: getattr(row, column.key)
        for column in inspect(row).mapper.column_attrs
        if column.key not in excluded
    }


def require_version(row: Any, expected: int) -> None:
    if row.version != expected:
        raise HTTPException(
            status_code=409,
            detail="Мэдээлэл өөр төхөөрөмж дээр шинэчлэгдсэн. Дахин ачаална уу",
        )


def validate_birth_year(birth_year: int) -> None:
    if birth_year > date.today().year:
        raise HTTPException(status_code=400, detail="Төрсөн он ирээдүйд байж болохгүй")


def validate_horse_links(
    db: Session,
    *,
    group_id: str,
    birth_year: int,
    mother_id: str | None,
    father_id: str | None,
    horse_id: str | None = None,
) -> None:
    group = db.get(HorseGroup, group_id)
    if group is None or not group.is_active:
        raise HTTPException(status_code=404, detail="Идэвхтэй азарганы бүлэг олдсонгүй")
    for key, parent_id in (("mother", mother_id), ("father", father_id)):
        if not parent_id:
            continue
        if parent_id == horse_id:
            raise HTTPException(
                status_code=400, detail="Мал өөрөө өөрийнхөө төл байж болохгүй"
            )
        parent = db.get(Horse, parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Эцэг/эх адуу олдсонгүй")
        if key == "mother" and parent.sex != "FEMALE":
            raise HTTPException(status_code=400, detail="Эх адуу эм хүйстэй байх ёстой")
        if key == "father" and not (
            parent.sex == "MALE" and parent.male_status == "STALLION"
        ):
            raise HTTPException(status_code=400, detail="Эцэг адуу азарга байх ёстой")
        if parent.birth_year > birth_year - 2:
            raise HTTPException(
                status_code=400,
                detail="Эцэг/эхийн төрсөн он төлөөс дор хаяж 2 жилийн өмнө байна",
            )
        seen = {horse_id} if horse_id else set()
        stack = [parent]
        while stack:
            current = stack.pop()
            if current.id in seen:
                raise HTTPException(
                    status_code=400,
                    detail="Удам угсааны тойрог холбоос үүсэх боломжгүй",
                )
            seen.add(current.id)
            for ancestor_id in (current.mother_id, current.father_id):
                if ancestor_id:
                    ancestor = db.get(Horse, ancestor_id)
                    if ancestor:
                        stack.append(ancestor)


def validate_cattle_state(
    db: Session,
    *,
    sex: str,
    is_bull: bool,
    birth_year: int,
    mother_id: str | None,
    cattle_id: str | None = None,
) -> None:
    validate_birth_year(birth_year)
    if is_bull and sex != "MALE":
        raise HTTPException(status_code=400, detail="Бух заавал эр хүйстэй байна")
    if mother_id:
        if mother_id == cattle_id:
            raise HTTPException(
                status_code=400, detail="Үхэр өөрөө өөрийнхөө эх байж болохгүй"
            )
        mother = db.get(Cattle, mother_id)
        if mother is None or mother.sex != "FEMALE":
            raise HTTPException(status_code=400, detail="Эх үнээ буруу")
        if mother.birth_year > birth_year - 2:
            raise HTTPException(
                status_code=400, detail="Эх үнээ тугалаас дор хаяж 2 жилийн ах байна"
            )


def small_count_dict(row: SmallLivestockCount) -> dict[str, Any]:
    lambs = row.male_lamb + row.female_lamb
    kids = row.male_kid + row.female_kid
    if row.count_type == "EVENING":
        sheep_total = row.evening_sheep_total or 0
        goat_total = row.evening_goat_total or 0
        adult_total = None
    else:
        # Non-overlapping model: sheep_male/female and goat_male/female exclude
        # breeding males, hoggets/yearling goats, and offspring.
        sheep_total = row.sheep_male + row.sheep_female + row.ram + row.hogget + lambs
        goat_total = (
            row.goat_male + row.goat_female + row.buck + row.yearling_goat + kids
        )
        adult_total = sheep_total + goat_total - lambs - kids
    return {
        **model_snapshot(row),
        "total": sheep_total + goat_total,
        "sheep_total": sheep_total,
        "goat_total": goat_total,
        "male_sheep_total": row.sheep_male + row.ram,
        "female_sheep_total": row.sheep_female,
        "male_goat_total": row.goat_male + row.buck,
        "female_goat_total": row.goat_female,
        "lamb_total": lambs,
        "kid_total": kids,
        "adult_total": adult_total,
    }
