from io import BytesIO
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import zipfile

from PIL import Image

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


def png_bytes(color=(90, 130, 70)):
    output = BytesIO()
    Image.new("RGB", (80, 60), color).save(output, format="PNG")
    return output.getvalue()


def test_horse_and_cattle_profile_images_have_refreshable_signed_objects(
    client, horse_worker, cattle_worker
):
    horse = make_horse(client, horse_worker)
    uploaded_horse = client.post(
        f"/api/v1/horses/{horse['id']}/images",
        headers=headers(horse_worker),
        files={"files": ("horse.png", png_bytes(), "image/png")},
    )
    assert uploaded_horse.status_code == 200, uploaded_horse.text
    horse_profile = uploaded_horse.json()
    assert horse_profile["main_image"]["kind"] == "MAIN"
    assert horse_profile["layout_image"]["kind"] == "LAYOUT"
    signed_url = horse_profile["main_image"]["url"]
    image = client.get(signed_url)
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/webp")
    assert (
        client.get(
            f"/api/v1/images/{horse_profile['main_image']['id']}/content",
            params={"expires": 1, "signature": "invalid"},
        ).status_code
        == 403
    )

    parts = urlsplit(signed_url)
    query = parse_qs(parts.query)
    query["expires"] = ["1"]
    expired = urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, doseq=True),
            parts.fragment,
        )
    )
    assert client.get(expired).status_code == 403
    refreshed = client.get(
        f"/api/v1/horses/{horse['id']}", headers=headers(horse_worker)
    ).json()
    assert refreshed["main_image"]["url"] != expired

    cattle = client.post(
        "/api/v1/cattle",
        headers=headers(cattle_worker),
        json={
            "ear_tag": "IMAGE-CATTLE",
            "color": "Бор",
            "birth_year": 2022,
            "sex": "FEMALE",
        },
    ).json()
    uploaded_cattle = client.post(
        f"/api/v1/cattle/{cattle['id']}/images",
        headers=headers(cattle_worker),
        files={"files": ("cattle.png", png_bytes((120, 80, 50)), "image/png")},
    )
    assert uploaded_cattle.status_code == 200, uploaded_cattle.text
    cattle_profile = uploaded_cattle.json()
    assert cattle_profile["main_image"]["kind"] == "MAIN"
    assert cattle_profile["layout_image"]["kind"] == "LAYOUT"
    assert client.get(cattle_profile["layout_image"]["url"]).status_code == 200
    assert (
        client.get(
            f"/api/v1/cattle/{cattle['id']}", headers=headers(horse_worker)
        ).status_code
        == 403
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
