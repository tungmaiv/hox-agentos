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
        from importlib import reload
        import core.config as config_module

        reload(config_module)
        config_module.get_settings.cache_clear()
        s = config_module.Settings()

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
