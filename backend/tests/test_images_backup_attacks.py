from io import BytesIO
import zipfile

from tests.conftest import headers


def make_horse(client, token):
    group = client.post(
        "/api/v1/horses/groups",
        headers=headers(token),
        json={"name": "Image validation"},
    ).json()
    return client.post(
        "/api/v1/horses",
        headers=headers(token),
        json={
            "group_id": group["id"],
            "color": "Хээр",
            "birth_year": 2024,
            "sex": "MALE",
            "male_status": "COLT",
        },
    ).json()


def test_image_mime_spoof_and_malformed_content_rejected(client, horse_worker):
    horse = make_horse(client, horse_worker)
    spoofed = client.post(
        f"/api/v1/horses/{horse['id']}/images",
        headers=headers(horse_worker),
        files={"files": ("not-image.png", b"this is not a png", "image/png")},
    )
    assert spoofed.status_code == 400
    assert (
        client.get(
            f"/api/v1/horses/{horse['id']}", headers=headers(horse_worker)
        ).json()["images"]
        == []
    )


def test_malformed_and_traversal_backups_rejected(client, owner):
    malformed = client.post(
        "/api/v1/backup/restore",
        headers=headers(owner),
        data={"confirmation": "RESTORE"},
        files={"file": ("broken.zip", b"not-a-zip", "application/zip")},
    )
    assert malformed.status_code == 400

    traversal = BytesIO()
    with zipfile.ZipFile(traversal, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../outside.txt", "blocked")
        archive.writestr("manifest.json", "{}")
        archive.writestr("data.json", "{}")
    rejected = client.post(
        "/api/v1/backup/restore",
        headers=headers(owner),
        data={"confirmation": "RESTORE"},
        files={"file": ("traversal.zip", traversal.getvalue(), "application/zip")},
    )
    assert rejected.status_code == 400


def test_worker_cannot_download_or_restore_backup(client, horse_worker):
    assert (
        client.get("/api/v1/backup", headers=headers(horse_worker)).status_code == 403
    )
    assert (
        client.post(
            "/api/v1/backup/restore",
            headers=headers(horse_worker),
            data={"confirmation": "RESTORE"},
            files={"file": ("empty.zip", b"", "application/zip")},
        ).status_code
        == 403
    )


def test_owner_reports_are_real_files_and_worker_is_denied(client, owner, horse_worker):
    excel = client.get("/api/v1/reports/excel", headers=headers(owner))
    pdf = client.get("/api/v1/reports/pdf", headers=headers(owner))
    assert excel.status_code == 200 and excel.content.startswith(b"PK")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert (
        client.get("/api/v1/reports/excel", headers=headers(horse_worker)).status_code
        == 403
    )
