import os
import uuid

import httpx
import pytest

from app.services.storage import (
    check_storage_ready,
    create_supabase_signed_url,
    delete_object,
    read_object,
    restore_object,
    save_object,
)


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not all(
        os.environ.get(name)
        for name in (
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_STORAGE_BUCKET",
        )
    ),
    reason="live Supabase credentials are not configured",
)
def test_private_supabase_storage_lifecycle():
    prefix = f"integration-tests/{uuid.uuid4().hex}"
    key = f"{prefix}/image.webp"
    original = b"RIFF-live-storage-test-WEBP"
    replacement = b"RIFF-live-storage-replacement-WEBP"
    try:
        check_storage_ready()
        save_object(original, key)
        assert read_object(key) == original

        signed_url = create_supabase_signed_url(key, expires_in=60)
        signed_response = httpx.get(signed_url, timeout=15)
        assert signed_response.status_code == 200
        assert signed_response.content == original

        public_url = (
            f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1/object/public/"
            f"{os.environ['SUPABASE_STORAGE_BUCKET']}/{key}"
        )
        assert httpx.get(public_url, timeout=15).status_code in {400, 401, 403, 404}

        restore_object(replacement, key)
        assert read_object(key) == replacement
    finally:
        delete_object(key)
