# backend/security/credentials.py
"""
AES-256-GCM credential vault for OAuth tokens.

SECURITY INVARIANTS:
- Tokens are NEVER logged (no structlog calls with token content)
- Tokens are NEVER returned to the frontend or passed to LLMs
- user_id is ALWAYS from JWT (never from request body or function args from user input)
- Each encryption uses a fresh random IV (prevents ciphertext reuse attacks)
- AES-GCM provides both encryption and authenticity (tampered ciphertext raises an error)

Key management: The encryption key is stored in settings.credential_encryption_key
as a hex-encoded 32-byte value. For MVP this is a single app-wide key. Key rotation
(KMS) is a post-MVP concern per CLAUDE.md constraints.
"""
import os
from uuid import UUID

import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.credentials import UserCredential

logger = structlog.get_logger(__name__)

# Nonce size for AES-GCM: 12 bytes (96 bits) is the NIST recommended size
_GCM_NONCE_SIZE = 12


def _get_key() -> bytes:
    """
    Retrieve the AES-256 encryption key (32 bytes) from environment/settings.

    The key is stored as hex in CREDENTIAL_ENCRYPTION_KEY env var.
    32 bytes = 64 hex characters.
    """
    hex_key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "")
    if not hex_key:
        # Try to import from settings
        try:
            from core.config import settings
            hex_key = settings.credential_encryption_key
        except Exception:
            pass

    if not hex_key:
        raise RuntimeError(
            "CREDENTIAL_ENCRYPTION_KEY is not set. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    key_bytes = bytes.fromhex(hex_key)
    if len(key_bytes) != 32:
        raise ValueError(f"Encryption key must be 32 bytes (AES-256), got {len(key_bytes)}")
    return key_bytes


def encrypt_token(token: str) -> tuple[bytes, bytes]:
    """
    Encrypt a token string using AES-256-GCM.

    Returns:
        (ciphertext, iv) — both as bytes
        iv is random per call (12 bytes / 96 bits per NIST SP 800-38D)
        ciphertext includes the GCM authentication tag

    Never logs the token or ciphertext.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    iv = os.urandom(_GCM_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(iv, token.encode("utf-8"), None)
    logger.debug("token_encrypted", ciphertext_length=len(ciphertext))
    return ciphertext, iv


def decrypt_token(ciphertext: bytes, iv: bytes) -> str:
    """
    Decrypt a token using AES-256-GCM.

    Raises:
        cryptography.exceptions.InvalidTag if ciphertext is tampered or IV is wrong.

    Never logs the decrypted token value.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    plaintext_bytes = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext_bytes.decode("utf-8")


async def store_credential(
    session: AsyncSession,
    *,
    user_id: UUID,
    provider: str,
    token: str,
) -> None:
    """
    Encrypt and persist a credential (upsert: insert or update).

    Args:
        session: Async DB session
        user_id: From JWT — NEVER from request body
        provider: 'google' | 'microsoft' | etc.
        token: OAuth token (plaintext) — encrypted before storage

    Logs the operation WITHOUT the token value.

    Uses select-then-insert/update pattern for cross-DB compatibility
    (SQLite does not support PostgreSQL ON CONFLICT DO UPDATE syntax).
    """
    ciphertext, iv = encrypt_token(token)

    # SQLite-compatible upsert: select-then-insert/update
    result = await session.execute(
        select(UserCredential).where(
            UserCredential.user_id == user_id,
            UserCredential.provider == provider,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.ciphertext = ciphertext
        existing.iv = iv
        await session.commit()
    else:
        credential = UserCredential(
            user_id=user_id,
            provider=provider,
            ciphertext=ciphertext,
            iv=iv,
        )
        session.add(credential)
        await session.commit()

    logger.info(
        "credential_stored",
        user_id=str(user_id),
        provider=provider,
        # Never log token, ciphertext, or iv
    )


async def get_credential(
    session: AsyncSession,
    *,
    user_id: UUID,
    provider: str,
) -> str | None:
    """
    Retrieve and decrypt a credential.

    Returns the decrypted token string, or None if no credential found.

    Isolation: WHERE user_id=$1 from JWT — user_id NEVER from caller input.
    """
    result = await session.execute(
        select(UserCredential).where(
            UserCredential.user_id == user_id,
            UserCredential.provider == provider,
        )
    )
    row = result.scalar_one_or_none()

    if row is None:
        return None

    token = decrypt_token(row.ciphertext, row.iv)
    logger.debug("credential_retrieved", user_id=str(user_id), provider=provider)
    # Never log the decrypted token
    return token


async def delete_credential(
    session: AsyncSession,
    *,
    user_id: UUID,
    provider: str,
) -> bool:
    """
    Delete a user's credential for a provider.

    Returns True if a row was deleted, False if no matching row found.
    Isolation: WHERE user_id=$1 enforced — only deletes the caller's credential.
    """
    result = await session.execute(
        select(UserCredential).where(
            UserCredential.user_id == user_id,
            UserCredential.provider == provider,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False

    await session.delete(row)
    await session.commit()
    logger.info("credential_deleted", user_id=str(user_id), provider=provider)
    return True
