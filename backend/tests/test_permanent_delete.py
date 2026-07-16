from datetime import date

from app.database import SessionLocal
from app.models import AuditLog, Cattle, Horse, HorseGroupTransfer, ImageAsset
from app.audit import deserialize
from tests.conftest import headers


def create_group(client, token, name="Permanent delete"):
    response = client.post(
        "/api/v1/horses/groups", headers=headers(token), json={"name": name}
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_horse(client, token, group_id, color="Хээр"):
    response = client.post(
        "/api/v1/horses",
        headers=headers(token),
        json={
            "group_id": group_id,
            "color": color,
            "birth_year": date.today().year - 2,
            "sex": "MALE",
            "male_status": "GELDING",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_cattle(client, token, ear_tag="DELETE-1"):
    response = client.post(
        "/api/v1/cattle",
        headers=headers(token),
        json={
            "ear_tag": ear_tag,
            "color": "Алаг",
            "birth_year": date.today().year - 2,
            "sex": "FEMALE",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_permanent_delete_requires_owner_archive_and_confirmation(
    client, owner, horse_worker, cattle_worker
):
    group = create_group(client, horse_worker)
    horse = create_horse(client, horse_worker, group["id"])
    cattle = create_cattle(client, cattle_worker)

    active_horse = client.request(
        "DELETE",
        f"/api/v1/horses/{horse['id']}/permanent",
        headers=headers(owner),
        json={"confirmation": "УСТГАХ"},
    )
    active_cattle = client.request(
        "DELETE",
        f"/api/v1/cattle/{cattle['id']}/permanent",
        headers=headers(owner),
        json={"confirmation": "УСТГАХ"},
    )
    assert active_horse.status_code == active_cattle.status_code == 409

    client.post(
        f"/api/v1/horses/{horse['id']}/archive",
        headers=headers(horse_worker),
        json={"archive_note": "test"},
    )
    assert (
        client.request(
            "DELETE",
            f"/api/v1/horses/{horse['id']}/permanent",
            headers=headers(horse_worker),
            json={"confirmation": "УСТГАХ"},
        ).status_code
        == 403
    )
    assert (
        client.request(
            "DELETE",
            f"/api/v1/horses/{horse['id']}/permanent",
            headers=headers(owner),
            json={"confirmation": "delete"},
        ).status_code
        == 422
    )


def test_owner_permanently_deletes_archived_horse_with_history_and_audit(
    client, owner, horse_worker
):
    first = create_group(client, horse_worker, "Delete first")
    second = create_group(client, horse_worker, "Delete second")
    horse = create_horse(client, horse_worker, first["id"], "Бор")
    moved = client.post(
        f"/api/v1/horses/{horse['id']}/transfer",
        headers=headers(horse_worker),
        json={
            "to_group_id": second["id"],
            "reason": "history cleanup",
            "expected_version": horse["version"],
        },
    )
    assert moved.status_code == 200, moved.text
    client.post(
        f"/api/v1/horses/{horse['id']}/archive",
        headers=headers(horse_worker),
        json={"archive_note": "owner approved", "deceased": True},
    )
    deleted = client.request(
        "DELETE",
        f"/api/v1/horses/{horse['id']}/permanent",
        headers=headers(owner),
        json={"confirmation": "УСТГАХ"},
    )
    assert deleted.status_code == 200, deleted.text
    assert (
        client.get(f"/api/v1/horses/{horse['id']}", headers=headers(owner)).status_code
        == 404
    )
    with SessionLocal() as db:
        assert db.get(Horse, horse["id"]) is None
        assert db.query(HorseGroupTransfer).filter_by(horse_id=horse["id"]).count() == 0
        audit = (
            db.query(AuditLog)
            .filter_by(
                action="PERMANENT_DELETE", entity_type="horse", entity_id=horse["id"]
            )
            .one()
        )
        snapshot = deserialize(audit.previous_data)
        assert audit.username == "Шүрэнчулуун"
        assert snapshot["record"]["current_status"] == "DECEASED"
        assert snapshot["record"]["color"] == "Бор"
        assert len(snapshot["transfers"]) == 2
        assert any(row["reason"] == "history cleanup" for row in snapshot["transfers"])
    assert (
        client.request(
            "DELETE",
            f"/api/v1/horses/{horse['id']}/permanent",
            headers=headers(owner),
            json={"confirmation": "УСТГАХ"},
        ).status_code
        == 404
    )


def test_owner_permanently_deletes_archived_cattle_and_detaches_offspring(
    client, owner, cattle_worker
):
    mother = create_cattle(client, cattle_worker, "MOTHER-DEL")
    child_response = client.post(
        "/api/v1/cattle",
        headers=headers(cattle_worker),
        json={
            "ear_tag": "CHILD-KEEP",
            "color": "Бор",
            "birth_year": date.today().year,
            "sex": "FEMALE",
            "mother_id": mother["id"],
        },
    )
    assert child_response.status_code == 200, child_response.text
    child = child_response.json()
    client.post(
        f"/api/v1/cattle/{mother['id']}/archive",
        headers=headers(cattle_worker),
        json={"archive_note": "owner approved"},
    )
    deleted = client.request(
        "DELETE",
        f"/api/v1/cattle/{mother['id']}/permanent",
        headers=headers(owner),
        json={"confirmation": "УСТГАХ"},
    )
    assert deleted.status_code == 200, deleted.text
    with SessionLocal() as db:
        assert db.get(Cattle, mother["id"]) is None
        assert db.get(Cattle, child["id"]).mother_id is None
        assert db.query(ImageAsset).filter_by(owner_id=mother["id"]).count() == 0
        audit = (
            db.query(AuditLog)
            .filter_by(
                action="PERMANENT_DELETE", entity_type="cattle", entity_id=mother["id"]
            )
            .one()
        )
        assert deserialize(audit.previous_data)["record"]["ear_tag"] == "MOTHER-DEL"
