"""
Shared pytest configuration and fixtures for the backend test suite.

Sets up a minimal environment so that Settings() can be instantiated without
a real .env file. The actual values don't matter for unit tests since they
are patched at the per-test level — we just need all required fields to be
present so the module-level `settings = get_settings()` in core/config.py
doesn't raise a ValidationError on import.
"""
import os

import pytest


# Set minimal env vars before any module imports happen.
# These are TEST values only — they never reach a real service.
_TEST_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+asyncpg://blitz:test@localhost/blitz_test",
    "REDIS_URL": "redis://localhost:6379",
    "KEYCLOAK_URL": "https://keycloak.blitz.local",
    "KEYCLOAK_REALM": "blitz-internal",
    "KEYCLOAK_CLIENT_ID": "blitz-agentos",
    "KEYCLOAK_CLIENT_SECRET": "test-secret",
    "LITELLM_URL": "http://localhost:4000",
    "LITELLM_MASTER_KEY": "test-key",
    "SECRET_KEY": "test-secret-key-32-chars-minimum!",
}

# Apply before collection — this ensures core.config.settings is importable
for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)
