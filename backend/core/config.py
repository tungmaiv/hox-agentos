"""
Core configuration for Blitz AgentOS.

Single source of truth for all settings and the ONLY entry point for LLM clients.
Never import provider SDKs (anthropic, openai) directly — always use get_llm().
"""
from functools import lru_cache

from langchain_openai import ChatOpenAI
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str
    redis_url: str

    # Keycloak
    keycloak_url: str
    keycloak_realm: str
    keycloak_client_id: str
    keycloak_client_secret: str
    keycloak_jwks_url: str = ""
    keycloak_issuer: str = ""
    # Path to CA cert for self-signed Keycloak TLS (local dev only).
    # Set this when Keycloak uses a self-signed cert not in the system trust store.
    keycloak_ca_cert: str = ""

    # LiteLLM
    litellm_url: str
    litellm_master_key: str

    # Security
    secret_key: str
    credential_encryption_key: str = ""  # Hex-encoded 32-byte key for AES-256-GCM

    # Application
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    audit_log_path: str = "logs/audit.jsonl"

    # Embedding
    embedding_model_path: str = "BAAI/bge-m3"  # Locked — 1024 dim; changing requires full reindex

    # Memory
    # Fallback when system_config DB key 'memory.episode_turn_threshold' is not set.
    # If total conversation turns reaches a multiple of this threshold, summarize_episode is triggered.
    episode_turn_threshold: int = 10

    # Channel sidecar URLs (Docker internal service names)
    telegram_gateway_url: str = "http://telegram-gateway:9001"
    whatsapp_gateway_url: str = "http://whatsapp-gateway:9002"
    teams_gateway_url: str = "http://teams-gateway:9003"

    @model_validator(mode="after")
    def derive_keycloak_urls(self) -> "Settings":
        """Derive JWKS and issuer URLs from keycloak_url and keycloak_realm."""
        base = f"{self.keycloak_url}/realms/{self.keycloak_realm}"
        if not self.keycloak_jwks_url:
            self.keycloak_jwks_url = f"{base}/protocol/openid-connect/certs"
        if not self.keycloak_issuer:
            self.keycloak_issuer = base
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def get_llm(alias: str) -> ChatOpenAI:
    """
    Single entry point for all LLM clients.

    Never import provider SDKs (anthropic, openai) directly in agent code.
    Always use this function to obtain an LLM client.

    Aliases map to LiteLLM proxy model names:
      blitz/master    → blitz-master   (Ollama qwen2.5:72b → Claude fallback)
      blitz/fast      → blitz-fast     (Ollama llama3.2:3b → gpt-4o-mini fallback)
      blitz/coder     → blitz-coder    (OpenRouter kimi-k1.5 → Claude fallback)
      blitz/summarizer→ blitz-summarizer (Ollama llama3.2:3b → gpt-4o-mini fallback)
    """
    model_map: dict[str, str] = {
        "blitz/master": "blitz-master",
        "blitz/fast": "blitz-fast",
        "blitz/coder": "blitz-coder",
        "blitz/summarizer": "blitz-summarizer",
    }
    model_name = model_map.get(alias, alias)
    return ChatOpenAI(
        model=model_name,
        base_url=f"{settings.litellm_url}/v1",
        api_key=settings.litellm_master_key,
        streaming=True,
    )
