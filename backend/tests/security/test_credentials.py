# backend/tests/security/test_credentials.py
"""
TDD tests for security/credentials.py AES-256-GCM vault.

Tests cover:
1. Cryptographic correctness (encrypt/decrypt round-trip)
2. Randomness (same plaintext -> different ciphertext each time)
3. DB CRUD with isolation (user A cannot read user B's credentials)

Uses aiosqlite in-memory DB — no live PostgreSQL required.
"""
import os
import pytest
import pytest_asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from core.db import Base

# Override encryption key for tests (32 bytes = AES-256)
TEST_ENCRYPTION_KEY = b"test_encryption_key_32bytes_here"  # exactly 32 bytes
assert len(TEST_ENCRYPTION_KEY) == 32, "Test key must be exactly 32 bytes for AES-256"

os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY.hex())


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite async session — no PostgreSQL required."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# -- Cryptographic unit tests (no DB needed) ------------------------------------

def test_encrypt_token_returns_ciphertext_and_iv():
    """encrypt_token() returns (ciphertext, iv) bytes tuple."""
    from security.credentials import encrypt_token

    ciphertext, iv = encrypt_token("my_secret_oauth_token")
    assert isinstance(ciphertext, bytes)
    assert isinstance(iv, bytes)
    assert len(iv) == 12, "AES-GCM IV must be 12 bytes (96 bits)"


def test_encrypt_token_ciphertext_differs_from_plaintext():
    """Encrypted ciphertext must not equal the plaintext encoded as bytes."""
    from security.credentials import encrypt_token

    plaintext = "super_secret_token_12345"
    ciphertext, _ = encrypt_token(plaintext)
    assert ciphertext != plaintext.encode(), "Ciphertext must not equal plaintext bytes!"


def test_encrypt_decrypt_round_trip():
    """decrypt_token(encrypt_token(x)) == x for any string x."""
    from security.credentials import encrypt_token, decrypt_token

    original = "oauth_access_token_abcdef_12345_xyz"
    ciphertext, iv = encrypt_token(original)
    recovered = decrypt_token(ciphertext, iv)
    assert recovered == original, f"Round-trip failed: expected '{original}', got '{recovered}'"


def test_encrypt_produces_different_ciphertext_each_time():
    """Same plaintext + different random IV -> different ciphertext each call."""
    from security.credentials import encrypt_token

    plaintext = "same_token_every_time"
    ciphertext_1, iv_1 = encrypt_token(plaintext)
    ciphertext_2, iv_2 = encrypt_token(plaintext)

    # IVs must differ (random per call)
    assert iv_1 != iv_2, "IVs must be random — same IV reuse breaks AES-GCM security!"
    # Ciphertexts must differ (because IVs differ)
    assert ciphertext_1 != ciphertext_2, "Same plaintext with different IVs must produce different ciphertexts"


def test_decrypt_with_wrong_iv_raises():
    """Decrypting with wrong IV must raise an error — data integrity check."""
    from security.credentials import encrypt_token, decrypt_token
    import pytest

    ciphertext, iv = encrypt_token("real_token")
    wrong_iv = bytes(12)  # All zeros — wrong IV

    with pytest.raises(Exception):
        decrypt_token(ciphertext, wrong_iv)


# -- DB CRUD tests --------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_and_get_credential_round_trip(db_session):
    """store_credential -> get_credential returns original plaintext token."""
    from security.credentials import store_credential, get_credential

    user_id = uuid4()
    original_token = "google_access_token_abc123"

    await store_credential(db_session, user_id=user_id, provider="google", token=original_token)
    recovered = await get_credential(db_session, user_id=user_id, provider="google")

    assert recovered == original_token, (
        f"Expected '{original_token}', got '{recovered}'"
    )


@pytest.mark.asyncio
async def test_get_credential_isolation_user_a_cannot_read_user_b(db_session):
    """CRITICAL: user_A cannot retrieve user_B's credentials."""
    from security.credentials import store_credential, get_credential

    user_a = uuid4()
    user_b = uuid4()

    await store_credential(db_session, user_id=user_b, provider="google", token="user_b_secret_token")

    # user_A queries same provider — must get None (not user_B's token)
    result = await get_credential(db_session, user_id=user_a, provider="google")
    assert result is None, (
        f"ISOLATION FAILURE: user_a got '{result}' from user_b's credential!"
    )


@pytest.mark.asyncio
async def test_get_credential_returns_none_for_missing(db_session):
    """get_credential returns None if no credential stored for that user+provider."""
    from security.credentials import get_credential

    result = await get_credential(db_session, user_id=uuid4(), provider="microsoft")
    assert result is None


@pytest.mark.asyncio
async def test_store_credential_upsert_updates_existing(db_session):
    """Storing a credential for the same user+provider overwrites the old one."""
    from security.credentials import store_credential, get_credential

    user_id = uuid4()
    await store_credential(db_session, user_id=user_id, provider="google", token="old_token")
    await store_credential(db_session, user_id=user_id, provider="google", token="new_token")

    result = await get_credential(db_session, user_id=user_id, provider="google")
    assert result == "new_token"


@pytest.mark.asyncio
async def test_delete_credential_removes_only_target_user(db_session):
    """delete_credential removes only the specified user's credential for that provider."""
    from security.credentials import store_credential, get_credential, delete_credential

    user_a = uuid4()
    user_b = uuid4()

    await store_credential(db_session, user_id=user_a, provider="google", token="token_a")
    await store_credential(db_session, user_id=user_b, provider="google", token="token_b")

    # Delete only user_a's credential
    await delete_credential(db_session, user_id=user_a, provider="google")

    # user_a's credential gone
    assert await get_credential(db_session, user_id=user_a, provider="google") is None
    # user_b's credential intact
    assert await get_credential(db_session, user_id=user_b, provider="google") == "token_b"
