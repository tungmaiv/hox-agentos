"""
Admin LLM model configuration — manages LiteLLM proxy models via API.

Endpoints:
  GET  /api/admin/llm/models  — list models from LiteLLM /model/info
  POST /api/admin/llm/models  — add model via LiteLLM /model/new
  DELETE /api/admin/llm/models/{model_alias} — delete via LiteLLM /model/delete

Security: requires tool:admin permission (it-admin role only — Gate 2).
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import httpx
from core.config import settings
from core.db import get_db
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/admin/llm", tags=["admin-llm"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AddModelRequest(BaseModel):
    model_alias: str
    provider_model: str
    api_base: str | None = None
    api_key: str | None = None


class ModelInfo(BaseModel):
    model_alias: str
    provider_model: str | None = None
    api_base: str | None = None


class LLMConfigResponse(BaseModel):
    models: list[ModelInfo]
    litellm_available: bool


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _litellm_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.litellm_master_key}"}


async def _require_admin(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require tool:admin permission (it-admin role only)."""
    if not await has_permission(user, "tool:admin", session):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/models", response_model=LLMConfigResponse)
async def get_models(
    user: UserContext = Depends(_require_admin),
) -> LLMConfigResponse:
    """
    Fetch current model list from LiteLLM proxy.

    Returns graceful empty state if LiteLLM is unavailable.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.litellm_url}/model/info",
                headers=_litellm_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            models: list[ModelInfo] = []
            for entry in data.get("data", []):
                models.append(
                    ModelInfo(
                        model_alias=entry.get("model_name", ""),
                        provider_model=entry.get("litellm_params", {}).get("model"),
                        api_base=entry.get("litellm_params", {}).get("api_base"),
                    )
                )
            return LLMConfigResponse(models=models, litellm_available=True)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("litellm_unavailable", error=str(exc))
        return LLMConfigResponse(models=[], litellm_available=False)


@router.post("/models", status_code=201)
async def add_model(
    request: AddModelRequest,
    user: UserContext = Depends(_require_admin),
) -> dict[str, str]:
    """
    Add a new model to LiteLLM proxy.

    Note: Changes are in-memory only unless LiteLLM is configured with a DB.
    For persistence across restarts, also update infra/litellm/config.yaml.
    """
    payload: dict[str, object] = {
        "model_name": request.model_alias,
        "litellm_params": {
            "model": request.provider_model,
            **({"api_base": request.api_base} if request.api_base else {}),
            **({"api_key": request.api_key} if request.api_key else {}),
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.litellm_url}/model/new",
            json=payload,
            headers=_litellm_headers(),
        )
        if resp.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail=f"LiteLLM error: {resp.text}",
            )
    logger.info(
        "llm_model_added",
        alias=request.model_alias,
        model=request.provider_model,
        user_id=str(user["user_id"]),
    )
    return {"status": "added", "model_alias": request.model_alias}


@router.delete("/models/{model_alias}", status_code=204)
async def delete_model(
    model_alias: str,
    user: UserContext = Depends(_require_admin),
) -> None:
    """
    Delete a model from LiteLLM proxy.

    Note: If LiteLLM is running without DB, the model reappears after restart
    if it is defined in config.yaml.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(
            f"{settings.litellm_url}/model/delete",
            json={"id": model_alias},
            headers=_litellm_headers(),
        )
        if resp.status_code not in (200, 204):
            raise HTTPException(
                status_code=502,
                detail=f"LiteLLM error: {resp.text}",
            )
    logger.info(
        "llm_model_deleted",
        alias=model_alias,
        user_id=str(user["user_id"]),
    )
