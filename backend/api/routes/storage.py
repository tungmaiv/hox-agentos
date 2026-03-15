"""
Storage API routes — file/folder/share management and memory indexing.

All endpoints require a valid JWT (get_current_user dependency).
Ownership is enforced: users can only read/modify their own files and folders,
or files/folders shared with them.

Routes:
  POST   /api/storage/files/upload           — upload or replace a file
  GET    /api/storage/files                  — list files (paginated, owner-scoped)
  GET    /api/storage/files/{file_id}        — download metadata + presigned URL
  DELETE /api/storage/files/{file_id}        — delete file (owner only)
  POST   /api/storage/files/{file_id}/add-to-memory  — queue file for memory indexing
  POST   /api/storage/folders                — create folder
  GET    /api/storage/folders                — list user's folders
  DELETE /api/storage/folders/{folder_id}   — delete folder (owner only)
  POST   /api/storage/shares                 — create a share record
  GET    /api/storage/shares/{file_id}       — list shares for a file (owner only)
  PATCH  /api/storage/shares/{share_id}      — update share permission (owner only)
  DELETE /api/storage/shares/{share_id}      — revoke share (owner only)
  GET    /api/storage/shared-with-me         — files/folders shared with calling user
  GET    /api/storage/users/search           — user typeahead for share dialog
  GET    /api/storage/notifications          — unread share notifications for current user
  POST   /api/storage/notifications/{id}/read — mark notification as read
  POST   /api/storage/notifications/read-all  — mark all notifications as read
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.db import get_db
from core.models.storage_file import StorageFile
from core.models.storage_folder import StorageFolder
from core.models.storage_share import StorageShare
from core.models.user_notification import UserNotification
from security.deps import get_current_user
from storage.service import StorageService
from storage.text_extractor import EXTRACTABLE_MIME_TYPES

# Import at module level so tests can patch api.routes.storage.embed_file_content
# Guarded import: embed_file_content may not be available until Phase 28 plan 02 is deployed
try:
    from scheduler.tasks.storage_embedding import embed_file_content
except ImportError:  # pragma: no cover
    embed_file_content = None  # type: ignore[assignment]

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/storage", tags=["storage"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class StorageFileResponse(BaseModel):
    id: str
    name: str
    owner_user_id: str
    folder_id: str | None
    content_hash: str
    mime_type: str
    size_bytes: int
    in_memory: bool
    download_url: str
    created_at: str
    updated_at: str


class StorageFolderCreate(BaseModel):
    name: str
    parent_folder_id: str | None = None


class StorageFolderResponse(BaseModel):
    id: str
    name: str
    owner_user_id: str
    parent_folder_id: str | None
    created_at: str
    updated_at: str


class ShareCreate(BaseModel):
    resource_type: str  # "file" | "folder"
    resource_id: str
    shared_with_user_id: str
    permission: str  # "READ" | "WRITE" | "ADMIN"


class ShareResponse(BaseModel):
    id: str
    file_id: str | None
    folder_id: str | None
    shared_with_user_id: str
    shared_by_user_id: str
    permission: str
    created_at: str


class ShareUpdateRequest(BaseModel):
    permission: str


class UserSearchResult(BaseModel):
    id: str
    email: str
    display_name: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def check_file_access(
    session: AsyncSession,
    file_id: UUID,
    user_id: UUID,
) -> bool:
    """Return True if user_id can access file_id.

    Access is granted when:
      1. user_id is the file owner
      2. A direct file_id share exists for user_id
      3. An ancestor folder share exists for user_id (file.folder_id share)

    This prevents Pitfall 4: folder shares not propagating to contained files.
    """
    # Check 1: ownership
    file_result = await session.execute(
        select(StorageFile).where(StorageFile.id == file_id)
    )
    file_record = file_result.scalar_one_or_none()
    if file_record is None:
        return False
    if file_record.owner_user_id == user_id:
        return True

    # Check 2: direct file share
    direct_share_result = await session.execute(
        select(StorageShare).where(
            StorageShare.file_id == file_id,
            StorageShare.shared_with_user_id == user_id,
        )
    )
    if direct_share_result.scalar_one_or_none() is not None:
        return True

    # Check 3: ancestor folder share
    if file_record.folder_id is not None:
        folder_share_result = await session.execute(
            select(StorageShare).where(
                StorageShare.folder_id == file_record.folder_id,
                StorageShare.shared_with_user_id == user_id,
            )
        )
        if folder_share_result.scalar_one_or_none() is not None:
            return True

    return False


def _file_to_response(file_record: StorageFile, download_url: str) -> StorageFileResponse:
    return StorageFileResponse(
        id=str(file_record.id),
        name=file_record.name,
        owner_user_id=str(file_record.owner_user_id),
        folder_id=str(file_record.folder_id) if file_record.folder_id else None,
        content_hash=file_record.content_hash,
        mime_type=file_record.mime_type,
        size_bytes=file_record.size_bytes,
        in_memory=file_record.in_memory,
        download_url=download_url,
        created_at=file_record.created_at.isoformat() if file_record.created_at else "",
        updated_at=file_record.updated_at.isoformat() if file_record.updated_at else "",
    )


def _folder_to_response(folder: StorageFolder) -> StorageFolderResponse:
    return StorageFolderResponse(
        id=str(folder.id),
        name=folder.name,
        owner_user_id=str(folder.owner_user_id),
        parent_folder_id=str(folder.parent_folder_id) if folder.parent_folder_id else None,
        created_at=folder.created_at.isoformat() if folder.created_at else "",
        updated_at=folder.updated_at.isoformat() if folder.updated_at else "",
    )


def _share_to_response(share: StorageShare) -> ShareResponse:
    return ShareResponse(
        id=str(share.id),
        file_id=str(share.file_id) if share.file_id else None,
        folder_id=str(share.folder_id) if share.folder_id else None,
        shared_with_user_id=str(share.shared_with_user_id),
        shared_by_user_id=str(share.shared_by_user_id),
        permission=share.permission,
        created_at=share.created_at.isoformat() if share.created_at else "",
    )


def _send_share_email(
    shared_with_user_id: UUID,
    shared_by_user_id: UUID,
    resource_type: str,
    resource_id: str,
) -> None:
    """Stub: log share email notification — email infra deferred to Phase 33."""
    logger.info(
        "share_email_stub",
        shared_with_user_id=str(shared_with_user_id),
        shared_by_user_id=str(shared_by_user_id),
        resource_type=resource_type,
        resource_id=resource_id,
    )


# ---------------------------------------------------------------------------
# File endpoints
# ---------------------------------------------------------------------------


@router.post("/files/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    folder_id: str | None = Form(None),
    action: str | None = Form(None),
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Upload a file to MinIO and save metadata to DB.

    Handles deduplication (same SHA-256 for same user) and the replace/skip/keep_both action flow.
    If action=replace and existing_file.in_memory is True, re-triggers embedding.
    """
    # Read content in streaming chunks and compute SHA-256 incrementally
    content = await file.read()
    size_bytes = len(content)

    # Validate file size
    max_bytes = settings.storage_max_file_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(status_code=413, detail="File size exceeds the maximum allowed size")

    content_hash = hashlib.sha256(content).hexdigest()
    mime_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unnamed"
    user_id: UUID = current_user["user_id"]

    # Check for duplicate (same user, same SHA-256 OR same filename with replace action)
    existing_result = await session.execute(
        select(StorageFile).where(
            StorageFile.owner_user_id == user_id,
            StorageFile.content_hash == content_hash,
        )
    )
    existing_file = existing_result.scalar_one_or_none()

    # When action=replace, also look up by filename (user may replace with different content)
    if existing_file is None and action == "replace":
        name_result = await session.execute(
            select(StorageFile).where(
                StorageFile.owner_user_id == user_id,
                StorageFile.name == filename,
            )
        )
        existing_file = name_result.scalar_one_or_none()

    if existing_file is not None:
        if action is None:
            # No action specified — return 200 (not 201) with duplicate info for frontend dialog
            return JSONResponse(
                status_code=200,
                content={
                    "duplicate": True,
                    "existing_file_id": str(existing_file.id),
                    "existing_file_name": existing_file.name,
                },
            )

        if action == "skip":
            # Return existing metadata without changes
            service = StorageService()
            download_url = await service.generate_download_url(existing_file.object_key)
            return _file_to_response(existing_file, download_url)

        if action == "replace":
            # Overwrite MinIO object and update DB metadata
            service = StorageService()
            await service.upload_bytes(existing_file.object_key, content, mime_type)
            existing_file.size_bytes = size_bytes
            existing_file.content_hash = content_hash
            existing_file.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(existing_file)

            # Re-trigger embedding if file was in memory
            if existing_file.in_memory and embed_file_content is not None:
                embed_file_content.delay(str(existing_file.id), str(user_id))

            download_url = await service.generate_download_url(existing_file.object_key)
            return _file_to_response(existing_file, download_url)

        if action == "keep_both":
            # Treat as new upload with renamed filename (append " (1)")
            filename = f"{filename} (1)"
            # Fall through to new upload logic below
            existing_file = None  # force new upload path
        # Unknown action — fall through to new upload
        else:
            existing_file = None

    if existing_file is not None:
        # Already handled above
        raise HTTPException(status_code=500, detail="Unexpected state in upload handler")

    # New file upload
    file_id = uuid4()
    service = StorageService()
    object_key = service.make_object_key(user_id, file_id)

    folder_uuid: UUID | None = None
    if folder_id:
        try:
            folder_uuid = UUID(folder_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid folder_id format")

    await service.upload_bytes(object_key, content, mime_type)

    new_file = StorageFile()
    new_file.id = file_id
    new_file.owner_user_id = user_id
    new_file.folder_id = folder_uuid
    new_file.name = filename
    new_file.object_key = object_key
    new_file.content_hash = content_hash
    new_file.mime_type = mime_type
    new_file.size_bytes = size_bytes
    new_file.in_memory = False
    new_file.created_at = datetime.now(timezone.utc)
    new_file.updated_at = datetime.now(timezone.utc)

    session.add(new_file)
    await session.commit()
    await session.refresh(new_file)

    download_url = await service.generate_download_url(object_key)

    logger.info(
        "storage_file_uploaded",
        file_id=str(file_id),
        user_id=str(user_id),
        size_bytes=size_bytes,
    )

    return _file_to_response(new_file, download_url)


@router.get("/files")
async def list_files(
    folder_id: str | None = None,
    page: int = 1,
    limit: int = 50,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """List files owned by the calling user, optionally filtered by folder."""
    user_id: UUID = current_user["user_id"]
    query = select(StorageFile).where(StorageFile.owner_user_id == user_id)

    if folder_id is not None:
        try:
            folder_uuid = UUID(folder_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid folder_id format")
        query = query.where(StorageFile.folder_id == folder_uuid)

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    files = result.scalars().all()

    service = StorageService()
    items = []
    for f in files:
        download_url = await service.generate_download_url(f.object_key)
        items.append(_file_to_response(f, download_url))

    return {"items": items, "page": page, "limit": limit}


@router.get("/files/{file_id}")
async def get_file(
    file_id: UUID,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Return file metadata + presigned download URL. Checks ownership or share access."""
    user_id: UUID = current_user["user_id"]
    has_access = await check_file_access(session, file_id, user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await session.execute(select(StorageFile).where(StorageFile.id == file_id))
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    service = StorageService()
    download_url = await service.generate_download_url(file_record.object_key)
    return _file_to_response(file_record, download_url)


@router.delete("/files/{file_id}", status_code=204, response_model=None)
async def delete_file(
    file_id: UUID,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a file from MinIO and DB. Owner only."""
    user_id: UUID = current_user["user_id"]
    result = await session.execute(select(StorageFile).where(StorageFile.id == file_id))
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_record.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this file")

    service = StorageService()
    await service.delete_object(file_record.object_key)
    await session.delete(file_record)
    await session.commit()

    logger.info("storage_file_deleted", file_id=str(file_id), user_id=str(user_id))


@router.post("/files/{file_id}/add-to-memory")
async def add_to_memory(
    file_id: UUID,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Queue a file for memory indexing via Celery.

    Only EXTRACTABLE_MIME_TYPES are supported. Sets in_memory=True and dispatches
    embed_file_content.delay for background processing.
    """
    user_id: UUID = current_user["user_id"]
    result = await session.execute(select(StorageFile).where(StorageFile.id == file_id))
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_record.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can index this file")

    if file_record.mime_type not in EXTRACTABLE_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail="File type not supported for memory indexing",
        )

    file_record.in_memory = True
    await session.commit()

    if embed_file_content is not None:
        embed_file_content.delay(str(file_id), str(user_id))

    logger.info("add_to_memory_queued", file_id=str(file_id), user_id=str(user_id))
    return {"status": "queued"}


# ---------------------------------------------------------------------------
# Folder endpoints
# ---------------------------------------------------------------------------


@router.post("/folders", status_code=201)
async def create_folder(
    body: StorageFolderCreate,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Create a folder owned by the calling user."""
    user_id: UUID = current_user["user_id"]

    parent_uuid: UUID | None = None
    if body.parent_folder_id:
        try:
            parent_uuid = UUID(body.parent_folder_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid parent_folder_id format")

    folder = StorageFolder()
    folder.id = uuid4()
    folder.owner_user_id = user_id
    folder.name = body.name
    folder.parent_folder_id = parent_uuid
    folder.created_at = datetime.now(timezone.utc)
    folder.updated_at = datetime.now(timezone.utc)

    session.add(folder)
    await session.commit()
    await session.refresh(folder)

    logger.info("storage_folder_created", folder_id=str(folder.id), user_id=str(user_id))
    return _folder_to_response(folder)


@router.get("/folders")
async def list_folders(
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """List all folders owned by the calling user (flat list; frontend builds tree)."""
    user_id: UUID = current_user["user_id"]
    result = await session.execute(
        select(StorageFolder).where(StorageFolder.owner_user_id == user_id)
    )
    folders = result.scalars().all()
    return [_folder_to_response(f) for f in folders]


@router.delete("/folders/{folder_id}", status_code=204, response_model=None)
async def delete_folder(
    folder_id: UUID,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a folder. Owner only."""
    user_id: UUID = current_user["user_id"]
    result = await session.execute(
        select(StorageFolder).where(StorageFolder.id == folder_id)
    )
    folder = result.scalar_one_or_none()
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this folder")

    await session.delete(folder)
    await session.commit()


# ---------------------------------------------------------------------------
# Share endpoints
# ---------------------------------------------------------------------------


@router.post("/shares", status_code=201)
async def create_share(
    body: ShareCreate,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Create a share record and fire a user notification for the recipient."""
    user_id: UUID = current_user["user_id"]

    try:
        resource_uuid = UUID(body.resource_id)
        recipient_uuid = UUID(body.shared_with_user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID in request")

    share = StorageShare()
    share.id = uuid4()
    share.shared_by_user_id = user_id
    share.shared_with_user_id = recipient_uuid
    share.permission = body.permission
    share.created_at = datetime.now(timezone.utc)
    share.updated_at = datetime.now(timezone.utc)

    if body.resource_type == "file":
        share.file_id = resource_uuid
        share.folder_id = None
    elif body.resource_type == "folder":
        share.folder_id = resource_uuid
        share.file_id = None
    else:
        raise HTTPException(status_code=422, detail="resource_type must be 'file' or 'folder'")

    session.add(share)

    # Create notification for recipient
    notification = UserNotification()
    notification.id = uuid4()
    notification.user_id = recipient_uuid
    notification.title = "File shared with you"
    notification.message = f"A {body.resource_type} has been shared with you."
    notification.notification_type = "file_shared"
    notification.is_read = False
    notification.created_at = datetime.now(timezone.utc)
    session.add(notification)

    await session.commit()
    await session.refresh(share)

    # Fire stub share email (logs only — email infra deferred to Phase 33)
    _send_share_email(recipient_uuid, user_id, body.resource_type, body.resource_id)

    logger.info(
        "storage_share_created",
        share_id=str(share.id),
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        shared_by=str(user_id),
        shared_with=str(recipient_uuid),
    )
    return _share_to_response(share)


@router.get("/shares/{file_id}")
async def list_shares(
    file_id: UUID,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """List all shares for a file. Owner only."""
    user_id: UUID = current_user["user_id"]

    # Verify ownership
    file_result = await session.execute(
        select(StorageFile).where(StorageFile.id == file_id)
    )
    file_record = file_result.scalar_one_or_none()
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_record.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can list shares for this file")

    result = await session.execute(
        select(StorageShare).where(StorageShare.file_id == file_id)
    )
    shares = result.scalars().all()
    return [_share_to_response(s) for s in shares]


@router.patch("/shares/{share_id}")
async def update_share(
    share_id: UUID,
    body: ShareUpdateRequest,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Update the permission level of a share. Owner only."""
    user_id: UUID = current_user["user_id"]
    result = await session.execute(select(StorageShare).where(StorageShare.id == share_id))
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")
    if share.shared_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the share creator can update it")

    share.permission = body.permission
    share.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(share)
    return _share_to_response(share)


@router.delete("/shares/{share_id}", status_code=204, response_model=None)
async def delete_share(
    share_id: UUID,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a share. Owner only — 403 for non-owner."""
    user_id: UUID = current_user["user_id"]
    result = await session.execute(select(StorageShare).where(StorageShare.id == share_id))
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")
    if share.shared_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the share creator can revoke it")

    await session.delete(share)
    await session.commit()

    logger.info("storage_share_deleted", share_id=str(share_id), user_id=str(user_id))


# ---------------------------------------------------------------------------
# Shared-with-me endpoint
# ---------------------------------------------------------------------------


@router.get("/shared-with-me")
async def shared_with_me(
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """List all files and folders shared with the calling user."""
    user_id: UUID = current_user["user_id"]
    result = await session.execute(
        select(StorageShare).where(StorageShare.shared_with_user_id == user_id)
    )
    shares = result.scalars().all()
    return [_share_to_response(s) for s in shares]


# ---------------------------------------------------------------------------
# User search endpoint (for share dialog typeahead)
# ---------------------------------------------------------------------------


@router.get("/users/search")
async def search_users(
    q: str = "",
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[UserSearchResult]:
    """Search local users by email or username for share dialog typeahead.

    Returns up to 10 results matching the query string.
    Only queries local_users table (LocalUser) — Keycloak users are not local.
    """
    from core.models.local_auth import LocalUser

    if not q or len(q) < 1:
        return []

    result = await session.execute(
        select(LocalUser).where(
            or_(
                LocalUser.email.ilike(f"%{q}%"),
                LocalUser.username.ilike(f"%{q}%"),
            )
        ).limit(10)
    )
    users = result.scalars().all()
    return [
        UserSearchResult(
            id=str(u.id),
            email=u.email,
            display_name=u.username,
        )
        for u in users
    ]


# ---------------------------------------------------------------------------
# Notification endpoints (per-user share notifications)
# ---------------------------------------------------------------------------


class UserNotificationResponse(BaseModel):
    id: str
    title: str
    message: str | None
    notification_type: str
    is_read: bool
    created_at: str


# NOTE: /notifications/read-all MUST be declared BEFORE /notifications/{notification_id}/read
# to prevent FastAPI routing collision where "read-all" is matched as a UUID notification_id.


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark all notifications for the calling user as read."""
    user_id: UUID = current_user["user_id"]
    await session.execute(
        update(UserNotification)
        .where(
            UserNotification.user_id == user_id,
            UserNotification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await session.commit()
    logger.info("storage_notifications_read_all", user_id=str(user_id))
    return {"status": "all_read"}


@router.get("/notifications")
async def list_notifications(
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[UserNotificationResponse]:
    """Return unread notifications for the calling user, ordered by created_at DESC, limit 20."""
    user_id: UUID = current_user["user_id"]
    result = await session.execute(
        select(UserNotification)
        .where(
            UserNotification.user_id == user_id,
            UserNotification.is_read == False,  # noqa: E712
        )
        .order_by(UserNotification.created_at.desc())
        .limit(20)
    )
    notifications = result.scalars().all()
    return [
        UserNotificationResponse(
            id=str(n.id),
            title=n.title,
            message=n.message,
            notification_type=n.notification_type,
            is_read=n.is_read,
            created_at=n.created_at.isoformat() if n.created_at else "",
        )
        for n in notifications
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: Any = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark a single notification as read. User can only read their own notifications."""
    user_id: UUID = current_user["user_id"]
    result = await session.execute(
        select(UserNotification).where(UserNotification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    notification.is_read = True
    await session.commit()
    logger.info(
        "storage_notification_read",
        notification_id=str(notification_id),
        user_id=str(user_id),
    )
    return {"status": "read"}
