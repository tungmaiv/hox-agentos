"""
Async S3 client singleton for MinIO access.

Usage:
    from storage.client import get_aioboto3_session
    session = get_aioboto3_session()
    async with session.client("s3", endpoint_url=...) as s3:
        ...

Never create aioboto3 clients at module level — always use async context managers.
"""
import aioboto3

_session: aioboto3.Session | None = None


def get_aioboto3_session() -> aioboto3.Session:
    """Return the module-level aioboto3 Session singleton.

    Creates the session on first call; returns the same instance thereafter.
    Thread-safe for async single-process usage (no locking needed).
    """
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session
