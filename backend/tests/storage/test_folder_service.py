"""
TDD placeholder for storage folder model — Phase 28 (STOR-02).

RED phase: fails until StorageFolder ORM model is created.

Full folder service tests come in plan 02 when routes are added.
This file confirms the model is importable with the expected tablename.
"""
from __future__ import annotations


def test_storage_folder_tablename() -> None:
    """StorageFolder ORM model uses tablename 'storage_folders'."""
    from core.models.storage_folder import StorageFolder  # type: ignore[import]

    assert StorageFolder.__tablename__ == "storage_folders"


def test_storage_file_tablename() -> None:
    """StorageFile ORM model uses tablename 'storage_files'."""
    from core.models.storage_file import StorageFile  # type: ignore[import]

    assert StorageFile.__tablename__ == "storage_files"


def test_storage_share_tablename() -> None:
    """StorageShare ORM model uses tablename 'storage_shares'."""
    from core.models.storage_share import StorageShare  # type: ignore[import]

    assert StorageShare.__tablename__ == "storage_shares"


def test_storage_file_has_in_memory_column() -> None:
    """StorageFile.in_memory column exists (required for STOR-05 auto re-embedding)."""
    from core.models.storage_file import StorageFile  # type: ignore[import]

    assert hasattr(StorageFile, "in_memory")


def test_storage_file_has_content_hash_column() -> None:
    """StorageFile.content_hash column exists (required for STOR-03 SHA-256 dedup)."""
    from core.models.storage_file import StorageFile  # type: ignore[import]

    assert hasattr(StorageFile, "content_hash")


def test_storage_share_permission_column() -> None:
    """StorageShare.permission column exists (READ/WRITE/ADMIN — STOR-04)."""
    from core.models.storage_share import StorageShare  # type: ignore[import]

    assert hasattr(StorageShare, "permission")
