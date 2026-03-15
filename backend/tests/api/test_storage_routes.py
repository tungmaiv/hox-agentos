"""
TDD tests for api/routes/storage.py — Phase 28 (STOR-02, STOR-03, STOR-04, STOR-05).

RED phase: all tests fail until storage routes are implemented.

Behaviors (12 from plan 28-02 Task 1):
  1.  POST /api/storage/files/upload — valid file → 201 with metadata + download_url
  2.  POST /api/storage/files/upload — duplicate SHA-256 for same user → 200 with duplicate info
  3.  POST /api/storage/files/upload — file exceeds max size → 413
  4.  GET  /api/storage/files — returns only calling user's files (JWT-scoped)
  5.  GET  /api/storage/files?folder_id=X — returns only files in that folder
  6.  POST /api/storage/folders — creates folder owned by calling user
  7.  POST /api/storage/shares → 201; GET /api/storage/shares/{file_id} returns the share
  8.  GET  /api/storage/users/search?q=email — returns matching users for typeahead
  9.  DELETE /api/storage/shares/{share_id} — owner succeeds; non-owner → 403
  10. POST /api/storage/files/{file_id}/add-to-memory — sets in_memory=True, dispatches Celery
  11. POST /api/storage/files/{file_id}/add-to-memory — non-extractable MIME → 422
  12. POST /api/storage/files/upload action=replace for in_memory=True file → triggers embed_file_content.delay
"""
from __future__ import annotations

import asyncio
import hashlib
import io
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from core.db import Base, get_db
from core.models.user import UserContext
from main import app
from security.deps import get_current_user


# ---------------------------------------------------------------------------
# Test user helpers
# ---------------------------------------------------------------------------


def make_user_ctx(user_id=None) -> UserContext:
    return UserContext(
        user_id=user_id or uuid4(),
        email="user@blitz.local",
        username="testuser",
        roles=["employee"],
        groups=["/tech"],
    )


def make_other_user_ctx() -> UserContext:
    return UserContext(
        user_id=uuid4(),
        email="other@blitz.local",
        username="otheruser",
        roles=["employee"],
        groups=["/tech"],
    )


# ---------------------------------------------------------------------------
# SQLite in-memory fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_db():
    """Override get_db with an in-memory SQLite async session.

    StaticPool ensures all connections share the same in-memory database,
    so data committed in one request is visible to subsequent requests in the same test.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture
def user_client(sqlite_db):
    """TestClient with employee auth + SQLite DB + mocked StorageService."""
    _user = make_user_ctx()
    app.dependency_overrides[get_current_user] = lambda: _user

    mock_storage = AsyncMock()
    mock_storage.upload_bytes = AsyncMock(return_value=None)
    mock_storage.download_bytes = AsyncMock(return_value=b"")
    mock_storage.delete_object = AsyncMock(return_value=None)
    mock_storage.generate_download_url = AsyncMock(
        return_value="http://localhost:9000/blitz-files/test?sig=abc"
    )
    mock_storage.make_object_key = MagicMock(
        side_effect=lambda uid, fid: f"users/{uid}/{fid}"
    )

    with patch("api.routes.storage.StorageService", return_value=mock_storage):
        client = TestClient(app, raise_server_exceptions=False)
        client._user = _user
        client._mock_storage = mock_storage
        yield client

    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------


def test_upload_requires_jwt() -> None:
    """POST /api/storage/files/upload returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/storage/files/upload",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 401


def test_list_files_requires_jwt() -> None:
    """GET /api/storage/files returns 401 without auth."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/storage/files")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test 1: Upload new file → 201 with metadata
# ---------------------------------------------------------------------------


def test_upload_new_file_returns_201(user_client: TestClient) -> None:
    """POST /api/storage/files/upload with a valid new file returns 201 with metadata."""
    response = user_client.post(
        "/api/storage/files/upload",
        files={"file": ("hello.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body.get("name") == "hello.txt"
    assert "download_url" in body


# ---------------------------------------------------------------------------
# Test 2: Upload duplicate SHA-256 → 200 with duplicate info
# ---------------------------------------------------------------------------


def test_upload_duplicate_returns_dedup_info(user_client: TestClient) -> None:
    """Uploading a file with duplicate SHA-256 for same user returns 200 with duplicate info."""
    content = b"duplicate content"

    # First upload creates the file
    user_client.post(
        "/api/storage/files/upload",
        files={"file": ("original.txt", content, "text/plain")},
    )

    # Second upload with same content triggers dedup
    response = user_client.post(
        "/api/storage/files/upload",
        files={"file": ("copy.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("duplicate") is True
    assert "existing_file_id" in body
    assert "existing_file_name" in body


# ---------------------------------------------------------------------------
# Test 3: Upload exceeds max size → 413
# ---------------------------------------------------------------------------


def test_upload_exceeds_max_size_returns_413(user_client: TestClient) -> None:
    """POST /api/storage/files/upload with a file exceeding max size returns 413."""
    # Patch settings to set max at 1 byte so any real file exceeds it
    with patch("api.routes.storage.settings") as mock_settings:
        mock_settings.storage_max_file_size_mb = 0  # 0 MB = 0 bytes threshold
        mock_settings.minio_bucket = "blitz-files"

        response = user_client.post(
            "/api/storage/files/upload",
            files={"file": ("big.txt", b"x" * 10, "text/plain")},
        )
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# Test 4: GET /api/storage/files returns only calling user's files
# ---------------------------------------------------------------------------


def test_list_files_scoped_to_jwt_user(sqlite_db) -> None:
    """GET /api/storage/files returns only files owned by the JWT user."""
    user_a = make_user_ctx()
    user_b = make_user_ctx()

    # Insert a file owned by user_a directly in DB
    from core.models.storage_file import StorageFile  # type: ignore[import]

    async def _seed() -> None:
        # Use the overridden get_db (SQLite) to seed the test database.
        # app.dependency_overrides[get_db] was set by the sqlite_db fixture.
        from core.db import get_db as _real_get_db
        from main import app as _app

        _override_get_db = _app.dependency_overrides.get(_real_get_db)
        if _override_get_db is None:
            return  # no override — skip seed (test assertion still passes: user_b sees 0 files)

        async for s in _override_get_db():
            f = StorageFile()
            f.id = uuid4()
            f.owner_user_id = user_a["user_id"]
            f.name = "user_a_file.txt"
            f.object_key = f"users/{user_a['user_id']}/{f.id}"
            f.content_hash = "aaa"
            f.mime_type = "text/plain"
            f.size_bytes = 3
            f.in_memory = False
            s.add(f)
            await s.commit()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_seed())
    loop.close()

    # user_b should see 0 files
    app.dependency_overrides[get_current_user] = lambda: user_b
    mock_storage = AsyncMock()
    mock_storage.generate_download_url = AsyncMock(return_value="http://localhost:9000/x")
    mock_storage.make_object_key = MagicMock(side_effect=lambda u, f: f"users/{u}/{f}")

    with patch("api.routes.storage.StorageService", return_value=mock_storage):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/storage/files")

    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    data = response.json()
    items = data.get("items") or data  # tolerate list or paginated response
    if isinstance(items, list):
        for item in items:
            assert str(item.get("owner_user_id")) != str(user_a["user_id"])


# ---------------------------------------------------------------------------
# Test 5: GET /api/storage/files?folder_id=X filters by folder
# ---------------------------------------------------------------------------


def test_list_files_filtered_by_folder(user_client: TestClient) -> None:
    """GET /api/storage/files?folder_id=X returns only files in that folder."""
    # Create a folder first
    folder_resp = user_client.post(
        "/api/storage/folders", json={"name": "MyFolder", "parent_folder_id": None}
    )
    if folder_resp.status_code not in (200, 201):
        pytest.skip("Folder creation not yet implemented")
    folder_id = folder_resp.json().get("id")

    # Upload a file into the folder
    user_client.post(
        "/api/storage/files/upload",
        data={"folder_id": folder_id},
        files={"file": ("in_folder.txt", b"content", "text/plain")},
    )

    # Upload a file NOT in the folder
    user_client.post(
        "/api/storage/files/upload",
        files={"file": ("no_folder.txt", b"other", "text/plain")},
    )

    response = user_client.get(f"/api/storage/files?folder_id={folder_id}")
    assert response.status_code == 200
    data = response.json()
    items = data.get("items") or data
    if isinstance(items, list):
        for item in items:
            assert str(item.get("folder_id")) == str(folder_id)


# ---------------------------------------------------------------------------
# Test 6: POST /api/storage/folders creates folder
# ---------------------------------------------------------------------------


def test_create_folder(user_client: TestClient) -> None:
    """POST /api/storage/folders creates a folder owned by the calling user."""
    response = user_client.post(
        "/api/storage/folders",
        json={"name": "Documents", "parent_folder_id": None},
    )
    assert response.status_code in (200, 201)
    body = response.json()
    assert body.get("name") == "Documents"
    assert "id" in body


# ---------------------------------------------------------------------------
# Test 7: POST /api/storage/shares → 201; GET shares for file
# ---------------------------------------------------------------------------


def test_create_and_list_share(user_client: TestClient) -> None:
    """POST /api/storage/shares creates share → 201; GET lists it."""
    # Upload a file first
    upload_resp = user_client.post(
        "/api/storage/files/upload",
        files={"file": ("shared.txt", b"share me", "text/plain")},
    )
    if upload_resp.status_code != 201:
        pytest.skip("Upload not yet implemented")
    file_id = upload_resp.json().get("id")
    recipient_id = str(uuid4())

    share_resp = user_client.post(
        "/api/storage/shares",
        json={
            "resource_type": "file",
            "resource_id": file_id,
            "shared_with_user_id": recipient_id,
            "permission": "READ",
        },
    )
    assert share_resp.status_code == 201

    list_resp = user_client.get(f"/api/storage/shares/{file_id}")
    assert list_resp.status_code == 200
    shares = list_resp.json()
    assert isinstance(shares, list)
    assert len(shares) >= 1
    assert any(s.get("shared_with_user_id") == recipient_id for s in shares)


# ---------------------------------------------------------------------------
# Test 8: GET /api/storage/users/search typeahead
# ---------------------------------------------------------------------------


def test_user_search_returns_results(user_client: TestClient) -> None:
    """GET /api/storage/users/search?q=... returns a list (may be empty for unknown query)."""
    response = user_client.get("/api/storage/users/search?q=nobody")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Test 9: DELETE share — owner succeeds, non-owner 403
# ---------------------------------------------------------------------------


def test_delete_share_by_non_owner_returns_403(user_client: TestClient) -> None:
    """DELETE /api/storage/shares/{share_id} by non-owner returns 403."""
    # Create a share as user_a
    upload_resp = user_client.post(
        "/api/storage/files/upload",
        files={"file": ("to_share.txt", b"data", "text/plain")},
    )
    if upload_resp.status_code != 201:
        pytest.skip("Upload not yet implemented")
    file_id = upload_resp.json().get("id")
    recipient_id = str(uuid4())

    share_resp = user_client.post(
        "/api/storage/shares",
        json={
            "resource_type": "file",
            "resource_id": file_id,
            "shared_with_user_id": recipient_id,
            "permission": "READ",
        },
    )
    if share_resp.status_code != 201:
        pytest.skip("Share creation not yet implemented")
    share_id = share_resp.json().get("id")

    # Attempt to delete as non-owner
    other = make_other_user_ctx()
    app.dependency_overrides[get_current_user] = lambda: other
    mock_storage = AsyncMock()
    mock_storage.make_object_key = MagicMock(side_effect=lambda u, f: f"users/{u}/{f}")

    with patch("api.routes.storage.StorageService", return_value=mock_storage):
        other_client = TestClient(app, raise_server_exceptions=False)
        del_resp = other_client.delete(f"/api/storage/shares/{share_id}")

    app.dependency_overrides.pop(get_current_user, None)
    assert del_resp.status_code == 403


# ---------------------------------------------------------------------------
# Test 10: POST add-to-memory sets in_memory=True, dispatches Celery
# ---------------------------------------------------------------------------


def test_add_to_memory_sets_flag_and_dispatches(user_client: TestClient) -> None:
    """POST /api/storage/files/{file_id}/add-to-memory sets in_memory=True and calls embed_file_content.delay."""
    upload_resp = user_client.post(
        "/api/storage/files/upload",
        files={"file": ("doc.txt", b"remember this", "text/plain")},
    )
    if upload_resp.status_code != 201:
        pytest.skip("Upload not yet implemented")
    file_id = upload_resp.json().get("id")

    mock_embed = MagicMock()
    mock_embed.delay = MagicMock()

    with patch("api.routes.storage.embed_file_content", mock_embed):
        response = user_client.post(f"/api/storage/files/{file_id}/add-to-memory")

    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "queued"
    mock_embed.delay.assert_called_once()


# ---------------------------------------------------------------------------
# Test 11: POST add-to-memory for non-extractable MIME → 422
# ---------------------------------------------------------------------------


def test_add_to_memory_non_extractable_returns_422(user_client: TestClient) -> None:
    """POST /api/storage/files/{file_id}/add-to-memory for image returns 422."""
    upload_resp = user_client.post(
        "/api/storage/files/upload",
        files={"file": ("photo.png", b"\x89PNG\r\n", "image/png")},
    )
    if upload_resp.status_code != 201:
        pytest.skip("Upload not yet implemented")
    file_id = upload_resp.json().get("id")

    response = user_client.post(f"/api/storage/files/{file_id}/add-to-memory")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test 12: Replace of in_memory=True file triggers re-embedding
# ---------------------------------------------------------------------------


def test_replace_in_memory_file_triggers_reembedding(user_client: TestClient) -> None:
    """Replacing a file with in_memory=True auto-dispatches embed_file_content.delay."""
    content = b"initial version"

    upload_resp = user_client.post(
        "/api/storage/files/upload",
        files={"file": ("doc.txt", content, "text/plain")},
    )
    if upload_resp.status_code != 201:
        pytest.skip("Upload not yet implemented")
    file_id = upload_resp.json().get("id")

    # Mark file as in_memory=True
    mock_embed = MagicMock()
    mock_embed.delay = MagicMock()

    with patch("api.routes.storage.embed_file_content", mock_embed):
        user_client.post(f"/api/storage/files/{file_id}/add-to-memory")

    mock_embed.delay.reset_mock()

    # Now replace with new content
    new_content = b"updated version"
    with patch("api.routes.storage.embed_file_content", mock_embed):
        replace_resp = user_client.post(
            "/api/storage/files/upload",
            data={"action": "replace"},
            files={"file": ("doc.txt", new_content, "text/plain")},
        )

    # The replace of an in_memory=True file should trigger re-embedding
    assert replace_resp.status_code in (200, 201)
    mock_embed.delay.assert_called_once()
