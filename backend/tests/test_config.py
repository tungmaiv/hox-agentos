"""
Tests for core/config.py

Tests that Settings loads correctly from environment variables and
derives Keycloak URLs without requiring a running Keycloak instance.
"""
from unittest.mock import patch


def _minimal_env() -> dict[str, str]:
    """Minimal set of env vars required by Settings."""
    return {
        "DATABASE_URL": "postgresql+asyncpg://blitz:test@postgres/blitz",
        "REDIS_URL": "redis://redis:6379",
        "KEYCLOAK_URL": "http://keycloak:8080",
        "KEYCLOAK_REALM": "blitz",
        "KEYCLOAK_CLIENT_ID": "blitz-agentos",
        "KEYCLOAK_CLIENT_SECRET": "test-secret",
        "LITELLM_URL": "http://litellm:4000",
        "LITELLM_MASTER_KEY": "test-key",
        "SECRET_KEY": "test-secret-key-32-chars-minimum!",
    }


def test_settings_loads_required_fields() -> None:
    """Settings loads all required fields from environment variables."""
    env = _minimal_env()
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        s = Settings()

    assert s.database_url == env["DATABASE_URL"]
    assert s.redis_url == env["REDIS_URL"]
    assert s.keycloak_url == env["KEYCLOAK_URL"]
    assert s.keycloak_realm == env["KEYCLOAK_REALM"]
    assert s.litellm_url == env["LITELLM_URL"]
    assert s.litellm_master_key == env["LITELLM_MASTER_KEY"]


def test_settings_derives_keycloak_jwks_url() -> None:
    """Settings automatically derives keycloak_jwks_url from url + realm."""
    env = _minimal_env()
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        s = Settings()

    expected = "http://keycloak:8080/realms/blitz/protocol/openid-connect/certs"
    assert s.keycloak_jwks_url == expected


def test_settings_derives_keycloak_issuer() -> None:
    """Settings automatically derives keycloak_issuer from url + realm."""
    env = _minimal_env()
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        s = Settings()

    expected = "http://keycloak:8080/realms/blitz"
    assert s.keycloak_issuer == expected


def test_settings_respects_explicit_keycloak_urls() -> None:
    """Explicit keycloak_jwks_url and keycloak_issuer are NOT overridden."""
    env = {
        **_minimal_env(),
        "KEYCLOAK_JWKS_URL": "https://custom.jwks.url/certs",
        "KEYCLOAK_ISSUER": "https://custom.issuer",
    }
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        s = Settings()

    assert s.keycloak_jwks_url == "https://custom.jwks.url/certs"
    assert s.keycloak_issuer == "https://custom.issuer"


def test_settings_default_cors_origins() -> None:
    """Default cors_origins includes localhost:3000."""
    env = _minimal_env()
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        s = Settings()

    assert "http://localhost:3000" in s.cors_origins


def test_get_llm_returns_chatopenai_with_litellm_url() -> None:
    """get_llm() returns ChatOpenAI pointing at LiteLLM proxy, not provider directly."""
    env = _minimal_env()
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings, get_llm

        # Reload settings with test env
        s = Settings()

        # Temporarily override settings in the module
        import core.config as config_module

        original_settings = config_module.settings
        config_module.settings = s

        try:
            llm = get_llm("blitz/master")
            assert "litellm:4000" in str(llm.openai_api_base)
            assert llm.model_name == "blitz-master"
        finally:
            config_module.settings = original_settings


def test_get_llm_maps_all_aliases() -> None:
    """get_llm() maps all blitz/* aliases to their LiteLLM model names."""
    env = _minimal_env()
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings, get_llm

        s = Settings()
        import core.config as config_module

        original_settings = config_module.settings
        config_module.settings = s

        try:
            aliases = {
                "blitz/master": "blitz-master",
                "blitz/fast": "blitz-fast",
                "blitz/coder": "blitz-coder",
                "blitz/summarizer": "blitz-summarizer",
            }
            for alias, expected_model in aliases.items():
                llm = get_llm(alias)
                assert llm.model_name == expected_model, f"{alias} should map to {expected_model}"
        finally:
            config_module.settings = original_settings


def test_get_llm_returns_chatopenai_pointing_at_litellm() -> None:
    """get_llm() must return a ChatOpenAI client pointed at LiteLLM proxy, not a provider."""
    from core.config import get_llm

    llm = get_llm("blitz/master")
    # openai_api_base is the internal attribute name for base_url in langchain-openai
    base_url_str = str(llm.openai_api_base or "")
    assert "4000" in base_url_str or "litellm" in base_url_str, (
        f"Expected LiteLLM URL (port 4000 or 'litellm'), got: {base_url_str}"
    )


def test_get_llm_uses_correct_model_alias() -> None:
    """Each alias maps to the correct sanitized model name sent to LiteLLM."""
    from core.config import get_llm

    cases: dict[str, str] = {
        "blitz/master": "blitz-master",
        "blitz/fast": "blitz-fast",
        "blitz/coder": "blitz-coder",
        "blitz/summarizer": "blitz-summarizer",
    }
    for alias, expected_model in cases.items():
        llm = get_llm(alias)
        assert llm.model_name == expected_model, (
            f"alias='{alias}': expected model='{expected_model}', got='{llm.model_name}'"
        )


def test_get_llm_unknown_alias_passes_through() -> None:
    """An unknown alias is passed through unchanged — LiteLLM handles the error, not backend code."""
    from core.config import get_llm

    llm = get_llm("custom/my-model")
    assert llm.model_name == "custom/my-model", (
        f"Expected model to pass through unchanged, got: '{llm.model_name}'"
    )


# ---------------------------------------------------------------------------
# Tests for CREDENTIAL_ENCRYPTION_KEY validation (24-01)
# ---------------------------------------------------------------------------


def _minimal_env_with_key(key: str) -> dict[str, str]:
    """Minimal env with custom credential_encryption_key."""
    return {
        **_minimal_env(),
        "CREDENTIAL_ENCRYPTION_KEY": key,
    }


def test_valid_64_char_hex_key_passes() -> None:
    """Settings accepts a valid 64-char hex string (32 bytes AES-256)."""
    valid_key = "a" * 64
    env = _minimal_env_with_key(valid_key)
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        s = Settings()

    assert s.credential_encryption_key == valid_key


def test_invalid_key_too_short_raises() -> None:
    """Settings raises ValueError when key is too short."""
    import pytest

    env = _minimal_env_with_key("abc")
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        with pytest.raises(ValueError, match="64-char hex"):
            Settings()


def test_empty_key_passes() -> None:
    """Settings accepts an empty CREDENTIAL_ENCRYPTION_KEY (key is optional)."""
    env = _minimal_env_with_key("")
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        s = Settings()

    assert s.credential_encryption_key == ""


def test_non_hex_raises() -> None:
    """Settings raises ValueError when key contains non-hex characters."""
    import pytest

    env = _minimal_env_with_key("g" * 64)
    with patch.dict("os.environ", env, clear=True):
        from core.config import Settings

        with pytest.raises(ValueError):
            Settings()
