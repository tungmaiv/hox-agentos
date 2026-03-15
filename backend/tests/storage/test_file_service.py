"""
TDD tests for storage/service.py — Phase 28 (STOR-01, STOR-02, STOR-03).

RED phase: tests fail until storage/service.py is implemented.

Behaviors:
  - StorageService.make_object_key(user_id, file_id) returns "users/{user_id}/{file_id}"
  - get_aioboto3_session() returns the same Session instance on repeated calls (singleton)
  - generate_download_url() calls generate_presigned_url with minio_public_url as endpoint
  - generate_upload_url() calls generate_presigned_url with minio_internal_url as endpoint
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def test_make_object_key_format() -> None:
    """make_object_key(user_id, file_id) returns 'users/{user_id}/{file_id}'."""
    from storage.service import StorageService  # type: ignore[import]

    user_id = uuid4()
    file_id = uuid4()
    svc = StorageService()
    result = svc.make_object_key(user_id, file_id)
    assert result == f"users/{user_id}/{file_id}"


def test_get_aioboto3_session_is_singleton() -> None:
    """get_aioboto3_session() returns same Session instance on repeated calls."""
    from storage.client import get_aioboto3_session  # type: ignore[import]

    session_a = get_aioboto3_session()
    session_b = get_aioboto3_session()
    assert session_a is session_b


def test_generate_download_url_uses_public_url() -> None:
    """generate_download_url() uses minio_public_url as the S3 endpoint."""
    import asyncio

    from storage.service import StorageService  # type: ignore[import]

    mock_s3_client = AsyncMock()
    mock_s3_client.generate_presigned_url = AsyncMock(
        return_value="http://localhost:9000/blitz-files/key?sig=abc"
    )
    # The client is used as an async context manager
    mock_s3_client.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_s3_client.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_s3_client)

    with patch("storage.service.get_aioboto3_session", return_value=mock_session):
        svc = StorageService()
        result = asyncio.run(svc.generate_download_url("users/abc/def"))

    # Verify it was called with the public URL as endpoint
    call_kwargs = mock_session.client.call_args
    assert call_kwargs is not None
    endpoint_used = call_kwargs.kwargs.get("endpoint_url") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
    if endpoint_used is None:
        # Check keyword args
        endpoint_used = call_kwargs.kwargs.get("endpoint_url", "")
    assert "localhost:9000" in endpoint_used or "minio_public_url" in str(call_kwargs)


def test_generate_upload_url_uses_internal_url() -> None:
    """generate_upload_url() uses minio_internal_url as the S3 endpoint."""
    import asyncio

    from storage.service import StorageService  # type: ignore[import]

    mock_s3_client = AsyncMock()
    mock_s3_client.generate_presigned_url = AsyncMock(
        return_value="http://minio:9000/blitz-files/key?sig=xyz"
    )
    mock_s3_client.__aenter__ = AsyncMock(return_value=mock_s3_client)
    mock_s3_client.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.client = MagicMock(return_value=mock_s3_client)

    with patch("storage.service.get_aioboto3_session", return_value=mock_session):
        svc = StorageService()
        result = asyncio.run(svc.generate_upload_url("users/abc/def"))

    call_kwargs = mock_session.client.call_args
    assert call_kwargs is not None
    endpoint_used = call_kwargs.kwargs.get("endpoint_url", "")
    assert "minio:9000" in endpoint_used or "minio_internal_url" in str(call_kwargs)
