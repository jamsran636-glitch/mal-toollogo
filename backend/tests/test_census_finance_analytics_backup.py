from io import BytesIO
import json
import zipfile

from app.database import SessionLocal
from app.models import HorseGroup
from tests.conftest import TEST_ACCOUNTS, headers


def full_count_payload(**overrides):
    payload = {
        "count_type": "FULL",
        "count_date": "2026-07-15",
        "sheep_male": 10,
        "sheep_female": 20,
        "goat_male": 5,
        "goat_female": 15,
        "male_lamb": 2,
        "female_lamb": 3,
        "male_kid": 1,
        "female_kid": 2,
        "hogget": 4,
        "yearling_goat": 3,
        "ram": 1,
        "buck": 1,
    }
    payload.update(overrides)
    return payload


def test_census_rejects_negative_and_includes_all_nonoverlapping_categories(
    client, sheep_worker
):
    invalid = client.post(
        "/api/v1/small-livestock/counts",
        headers=headers(sheep_worker),
        json=full_count_payload(sheep_male=-1),
    )
    assert invalid.status_code == 422
    created = client.post(
        "/api/v1/small-livestock/counts",
        headers=headers(sheep_worker),
        json=full_count_payload(),
    )
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["total"] == 67
    assert row["adult_total"] == 59
    assert (
        client.post(
            "/api/v1/small-livestock/counts",
            headers=headers(sheep_worker),
            json=full_count_payload(),
        ).status_code
        == 409
    )
    corrected = client.patch(
        f"/api/v1/small-livestock/counts/{row['id']}",
        headers=headers(sheep_worker),
        json={
            **full_count_payload(sheep_male=11),
            "expected_version": row["version"],
            "correction_reason": "Тооллогын алдаа",
        },
    )
    assert corrected.status_code == 200 and corrected.json()["total"] == 68


def test_evening_and_mortality_permissions(client, owner, sheep_worker):
    evening = client.post(
        "/api/v1/small-livestock/counts",
        headers=headers(sheep_worker),
        json={
            "count_type": "EVENING",
            "count_date": "2026-07-16",
            "evening_sheep_total": 50,
            "evening_goat_total": 20,
        },
    )
    assert evening.status_code == 200 and evening.json()["total"] == 70
    loss = {
        "loss_date": "2026-07-16",
        "livestock_type": "SHEEP",
        "animal_category": "Хонь",
        "quantity": 2,
        "reason": "Өвчин",
    }
    assert (
        client.post(
            "/api/v1/small-livestock/losses", headers=headers(sheep_worker), json=loss
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/small-livestock/losses", headers=headers(owner), json=loss
        ).status_code
        == 200
    )


def test_finance_validation_update_and_dashboard_real_snapshots(client, owner):
    bad = client.post(
        "/api/v1/finance",
        headers=headers(owner),
        json={
            "entry_type": "EXPENSE",
            "amount": 100,
            "entry_date": "2026-07-15",
            "livestock_module": "cattle",
            "category": "INVALID",
            "description": "x",
        },
    )
    assert bad.status_code == 422
    income_response = client.post(
        "/api/v1/finance",
        headers=headers(owner),
        json={
            "entry_type": "INCOME",
            "amount": 1000000,
            "entry_date": "2026-07-15",
            "livestock_module": "cattle",
            "description": "Борлуулалт",
        },
    )
    assert income_response.status_code == 200
    expense = client.post(
        "/api/v1/finance",
        headers=headers(owner),
        json={
            "entry_type": "EXPENSE",
            "amount": 200000,
            "entry_date": "2026-07-15",
            "livestock_module": "cattle",
            "category": "Өвс тэжээлд",
            "description": "Өвс",
        },
    ).json()
    updated = client.patch(
        f"/api/v1/finance/{expense['id']}",
        headers=headers(owner),
        json={
            "entry_type": "EXPENSE",
            "amount": 250000,
            "entry_date": "2026-07-15",
            "livestock_module": "cattle",
            "category": "Өвс тэжээлд",
            "description": "Өвс шинэчилсэн",
            "expected_version": expense["version"],
        },
    )
    assert updated.status_code == 200
    assert (
        client.post(
            "/api/v1/analytics/snapshots",
            headers=headers(owner),
            json={
                "module": "cattle",
                "snapshot_date": "2025-01-01",
                "count": 42,
                "note": "Баталгаажуулсан үлдэгдэл",
            },
        ).status_code
        == 200
    )
    dashboard = client.get(
        "/api/v1/analytics/dashboard?year=2026", headers=headers(owner)
    ).json()
    assert dashboard["profit_by_livestock"]["cattle"]["profit"] == 750000
    assert dashboard["growth"] == [
        {"year": 2025, "horses": None, "cattle": 42, "small_livestock": None}
    ]


def test_dashboard_preferences_persist(client, owner):
    response = client.put(
        "/api/v1/analytics/preferences",
        headers=headers(owner),
        json={"visible_widgets": ["counts", "growth"]},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/analytics/preferences", headers=headers(owner)).json()[
        "visible_widgets"
    ] == ["counts", "growth"]


def test_archived_animals_and_finance_do_not_affect_current_dashboard(client, owner):
    group = client.post(
        "/api/v1/horses/groups",
        headers=headers(owner),
        json={"name": "Stats exclusion"},
    ).json()
    horses = []
    for color in ("Active horse", "Archived horse"):
        response = client.post(
            "/api/v1/horses",
            headers=headers(owner),
            json={
                "group_id": group["id"],
                "color": color,
                "birth_year": 2020,
                "sex": "MALE",
                "male_status": "GELDING",
            },
        )
        assert response.status_code == 200, response.text
        horses.append(response.json())
    cattle = []
    for tag in ("ACTIVE-STATS", "ARCHIVED-STATS"):
        response = client.post(
            "/api/v1/cattle",
            headers=headers(owner),
            json={
                "ear_tag": tag,
                "color": "Алаг",
                "birth_year": 2020,
                "sex": "MALE",
            },
        )
        assert response.status_code == 200, response.text
        cattle.append(response.json())
    client.post(
        f"/api/v1/horses/{horses[1]['id']}/archive",
        headers=headers(owner),
        json={"archive_note": "demo archive"},
    )
    client.post(
        f"/api/v1/cattle/{cattle[1]['id']}/archive",
        headers=headers(owner),
        json={"archive_note": "demo archive"},
    )
    finance = client.post(
        "/api/v1/finance",
        headers=headers(owner),
        json={
            "entry_type": "INCOME",
            "amount": 999999,
            "entry_date": "2026-07-15",
            "livestock_module": "horses",
            "description": "archived demo income",
        },
    ).json()
    client.post(
        f"/api/v1/finance/{finance['id']}/archive",
        headers=headers(owner),
        json={"archive_note": "demo archive"},
    )
    client.post(
        "/api/v1/analytics/snapshots",
        headers=headers(owner),
        json={
            "module": "horses",
            "snapshot_date": "2025-01-01",
            "count": 12,
            "note": "historical verified inventory",
        },
    )

    assert (
        client.get("/api/v1/horses/statistics", headers=headers(owner)).json()["total"]
        == 1
    )
    assert (
        client.get("/api/v1/cattle/statistics", headers=headers(owner)).json()["total"]
        == 1
    )
    dashboard = client.get(
        "/api/v1/analytics/dashboard?year=2026", headers=headers(owner)
    ).json()
    assert dashboard["livestock_counts"]["horses"] == 1
    assert dashboard["livestock_counts"]["cattle"] == 1
    assert dashboard["adult_males"]["horses"]["total"] == 1
    assert dashboard["adult_males"]["cattle"]["total"] == 1
    assert dashboard["profit_by_livestock"]["horses"]["profit"] == 0
    assert dashboard["growth"] == [
        {"year": 2025, "horses": 12, "cattle": None, "small_livestock": None}
    ]


def test_empty_backup_rejected_without_data_loss(client, owner):
    group = client.post(
        "/api/v1/horses/groups", headers=headers(owner), json={"name": "Preserve me"}
    )
    assert group.status_code == 200
    empty = BytesIO()
    with zipfile.ZipFile(empty, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {"schema_version": 2, "application": "mal-toollogo", "tables": []}
            ),
        )
        archive.writestr("data.json", "{}")
    rejected = client.post(
        "/api/v1/backup/restore",
        headers=headers(owner),
        data={"confirmation": "RESTORE"},
        files={"file": ("empty.zip", empty.getvalue(), "application/zip")},
    )
    assert rejected.status_code == 400
    with SessionLocal() as db:
        assert db.get(HorseGroup, group.json()["id"]) is not None


def test_valid_backup_round_trip(client, owner):
    before = client.post(
        "/api/v1/horses/groups", headers=headers(owner), json={"name": "Before backup"}
    ).json()
    backup = client.get("/api/v1/backup", headers=headers(owner))
    assert backup.status_code == 200
    after = client.post(
        "/api/v1/horses/groups", headers=headers(owner), json={"name": "After backup"}
    ).json()
    restored = client.post(
        "/api/v1/backup/restore",
        headers=headers(owner),
        data={"confirmation": "RESTORE"},
        files={"file": ("backup.zip", backup.content, "application/zip")},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["reauthentication_required"] == "true"
    owner_username, owner_code, _ = TEST_ACCOUNTS[0]
    fresh_token = client.post(
        "/api/v1/auth/login",
        json={"username": owner_username, "code": owner_code},
    ).json()["access_token"]
    rows = client.get("/api/v1/horses/groups", headers=headers(fresh_token)).json()
    ids = {row["id"] for row in rows}
    assert before["id"] in ids and after["id"] not in ids
