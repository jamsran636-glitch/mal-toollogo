from datetime import date
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.database import engine
from app.main import app

from app.services.domain import age_years, horse_age_category
from tests.conftest import headers


def create_group(client, token, name="Group A"):
    response = client.post(
        "/api/v1/horses/groups", headers=headers(token), json={"name": name}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_april_first_age_boundaries_and_classes():
    assert age_years(2025, date(2026, 3, 31)) == 0
    assert age_years(2025, date(2026, 4, 1)) == 1
    assert [horse_age_category(year) for year in range(6)] == [
        "Унага",
        "Даага",
        "Шүдлэн",
        "Хязаалан",
        "Соёолон",
        "Их нас",
    ]


def test_pregnant_horse_stays_active_and_tree_order(client, horse_worker):
    group = create_group(client, horse_worker)
    stallion = client.post(
        "/api/v1/horses",
        headers=headers(horse_worker),
        json={
            "group_id": group["id"],
            "color": "Хээр",
            "birth_year": 2018,
            "sex": "MALE",
            "male_status": "STALLION",
        },
    ).json()
    mare = client.post(
        "/api/v1/horses",
        headers=headers(horse_worker),
        json={
            "group_id": group["id"],
            "color": "Саарал",
            "birth_year": 2020,
            "sex": "FEMALE",
            "current_status": "PREGNANT",
            "father_id": stallion["id"],
        },
    ).json()
    foal = client.post(
        "/api/v1/horses",
        headers=headers(horse_worker),
        json={
            "group_id": group["id"],
            "color": "Хонгор",
            "birth_year": date.today().year,
            "sex": "MALE",
            "male_status": "COLT",
            "mother_id": mare["id"],
            "father_id": stallion["id"],
        },
    )
    assert foal.status_code == 200, foal.text
    stats = client.get(
        "/api/v1/horses/statistics", headers=headers(horse_worker)
    ).json()
    assert stats["total"] == 3
    tree = client.get("/api/v1/horses/tree", headers=headers(horse_worker)).json()[0][
        "horses"
    ]
    assert [row["id"] for row in tree[:3]] == [
        stallion["id"],
        mare["id"],
        foal.json()["id"],
    ]
    assert tree[2]["indent"] == 1


def test_horse_transfer_archive_restore_and_history(client, horse_worker):
    first = create_group(client, horse_worker, "First")
    second = create_group(client, horse_worker, "Second")
    horse = client.post(
        "/api/v1/horses",
        headers=headers(horse_worker),
        json={
            "group_id": first["id"],
            "color": "Бор",
            "birth_year": 2022,
            "sex": "MALE",
            "male_status": "GELDING",
        },
    ).json()
    moved = client.post(
        f"/api/v1/horses/{horse['id']}/transfer",
        headers=headers(horse_worker),
        json={
            "to_group_id": second["id"],
            "reason": "Бүлэг шинэчилсэн",
            "expected_version": horse["version"],
        },
    )
    assert moved.status_code == 200 and moved.json()["group_id"] == second["id"]
    history = client.get(
        f"/api/v1/horses/{horse['id']}/transfers", headers=headers(horse_worker)
    ).json()
    assert (
        history[0]["from_group_id"] == first["id"]
        and history[0]["to_group_id"] == second["id"]
    )
    archived = client.post(
        f"/api/v1/horses/{horse['id']}/archive",
        headers=headers(horse_worker),
        json={"archive_note": "Гарсан", "unnatural_loss": True, "deceased": True},
    )
    assert archived.json()["current_status"] == "DECEASED"
    restored = client.post(
        f"/api/v1/horses/{horse['id']}/restore",
        headers=headers(horse_worker),
        json={"reason": "Буруу архивласан"},
    )
    assert restored.status_code == 200 and restored.json()["current_status"] == "ACTIVE"


def test_horse_idempotency_prevents_duplicate(client, horse_worker):
    group = create_group(client, horse_worker)
    payload = {
        "group_id": group["id"],
        "color": "Хээр",
        "birth_year": 2023,
        "sex": "MALE",
        "male_status": "COLT",
    }
    first = client.post(
        "/api/v1/horses",
        headers=headers(horse_worker, idempotency_key="horse-op-1"),
        json=payload,
    )
    second = client.post(
        "/api/v1/horses",
        headers=headers(horse_worker, idempotency_key="horse-op-1"),
        json=payload,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.integration
@pytest.mark.skipif(
    engine.dialect.name != "postgresql", reason="PostgreSQL concurrency test"
)
def test_concurrent_idempotency_returns_one_horse(client, horse_worker):
    group = create_group(client, horse_worker, "Concurrent")
    payload = {
        "group_id": group["id"],
        "color": "Хонгор",
        "birth_year": 2024,
        "sex": "MALE",
        "male_status": "COLT",
    }

    def create():
        with TestClient(app) as concurrent_client:
            return concurrent_client.post(
                "/api/v1/horses",
                headers=headers(horse_worker, idempotency_key="postgres-concurrent-op"),
                json=payload,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: create(), range(2)))
    assert {response.status_code for response in responses} == {200}
    assert len({response.json()["id"] for response in responses}) == 1
    assert len(client.get("/api/v1/horses", headers=headers(horse_worker)).json()) == 1


def test_cattle_patch_revalidates_female_bull_and_restore(client, cattle_worker):
    created = client.post(
        "/api/v1/cattle",
        headers=headers(cattle_worker),
        json={
            "ear_tag": "A-1",
            "color": "Алаг",
            "birth_year": 2020,
            "sex": "MALE",
            "is_bull": True,
        },
    )
    assert created.status_code == 200, created.text
    row = created.json()
    invalid = client.patch(
        f"/api/v1/cattle/{row['id']}",
        headers=headers(cattle_worker),
        json={"expected_version": row["version"], "sex": "FEMALE"},
    )
    assert invalid.status_code == 400
    archived = client.post(
        f"/api/v1/cattle/{row['id']}/archive",
        headers=headers(cattle_worker),
        json={"archive_note": "Шилжүүлсэн"},
    )
    assert archived.status_code == 200
    restored = client.post(
        f"/api/v1/cattle/{row['id']}/restore",
        headers=headers(cattle_worker),
        json={"reason": "Буцаасан"},
    )
    assert restored.status_code == 200 and restored.json()["current_status"] == "ACTIVE"


def test_owner_and_worker_audit_actor_values(client, owner, horse_worker):
    group = create_group(client, horse_worker)
    response = client.patch(
        f"/api/v1/horses/groups/{group['id']}",
        headers=headers(owner),
        json={"expected_version": group["version"], "description": "Owner edit"},
    )
    assert response.status_code == 200
    logs = client.get(
        f"/api/v1/audit?entity_id={group['id']}", headers=headers(owner)
    ).json()
    update = next(row for row in logs if row["action"] == "UPDATE")
    assert update["username"] == "Шүрэнчулуун" and update["role"] == "OWNER"
    assert update["previous_data"]["description"] is None
    assert update["new_data"]["description"] == "Owner edit"
