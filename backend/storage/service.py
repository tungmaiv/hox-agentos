"""
StorageService — presigned URL generation and direct byte upload/download via MinIO.

All S3 clients are created per-operation inside async context managers.
Never use a module-level S3 client singleton — boto3/aioboto3 clients are NOT thread-safe.
"""
from uuid import UUID

import structlog

from core.config import get_settings
from storage.client import get_aioboto3_session

logger = structlog.get_logger(__name__)


class StorageService:
    """Provides presigned URL generation and byte-level upload/download for MinIO storage."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def make_object_key(self, user_id: UUID, file_id: UUID) -> str:
        """Return the S3 object key for a user-owned file.

        Format: ``users/{user_id}/{file_id}``
        """
        return f"users/{user_id}/{file_id}"

    async def generate_upload_url(
        self,
        object_key: str,
        expires_in: int = 600,
    ) -> str:
        """Generate a presigned PUT URL for direct client-to-MinIO upload.

        Uses the internal MinIO URL (Docker-internal) so the backend can sign the URL.
        The client will use a translated public URL — callers must substitute the host
        when returning this URL to frontend clients.
        """
        session = get_aioboto3_session()
        async with session.client(
            "s3",
            endpoint_url=self.settings.minio_internal_url,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            region_name="us-east-1",
        ) as s3:
            url: str = await s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.settings.minio_bucket, "Key": object_key},
                ExpiresIn=expires_in,
            )
        return url

    async def generate_download_url(
        self,
        object_key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned GET URL for direct client download from MinIO.

        Uses the public MinIO URL (localhost-accessible) so the browser can fetch directly.
        """
        session = get_aioboto3_session()
        async with session.client(
            "s3",
            endpoint_url=self.settings.minio_public_url,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            region_name="us-east-1",
        ) as s3:
            url: str = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.settings.minio_bucket, "Key": object_key},
                ExpiresIn=expires_in,
            )
        return url

    async def upload_bytes(
        self,
        object_key: str,
        content: bytes,
        content_type: str,
    ) -> None:
        """Upload raw bytes directly to MinIO (for server-side uploads)."""
        session = get_aioboto3_session()
        async with session.client(
            "s3",
            endpoint_url=self.settings.minio_internal_url,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            region_name="us-east-1",
        ) as s3:
            await s3.put_object(
                Bucket=self.settings.minio_bucket,
                Key=object_key,
                Body=content,
                ContentType=content_type,
            )
        logger.info("storage_upload", object_key=object_key, size=len(content))

    async def download_bytes(self, object_key: str) -> bytes:
        """Download raw bytes from MinIO."""
        session = get_aioboto3_session()
        async with session.client(
            "s3",
            endpoint_url=self.settings.minio_internal_url,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            region_name="us-east-1",
        ) as s3:
            response = await s3.get_object(
                Bucket=self.settings.minio_bucket,
                Key=object_key,
            )
            body: bytes = await response["Body"].read()
        logger.info("storage_download", object_key=object_key, size=len(body))
        return body

    async def delete_object(self, object_key: str) -> None:
        """Delete an object from MinIO."""
        session = get_aioboto3_session()
        async with session.client(
            "s3",
            endpoint_url=self.settings.minio_internal_url,
            aws_access_key_id=self.settings.minio_access_key,
            aws_secret_access_key=self.settings.minio_secret_key,
            region_name="us-east-1",
        ) as s3:
            await s3.delete_object(
                Bucket=self.settings.minio_bucket,
                Key=object_key,
            )
        logger.info("storage_delete", object_key=object_key)
