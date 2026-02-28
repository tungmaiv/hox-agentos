# backend/agents/artifact_builder_validation.py
"""
Validation helpers for the artifact builder agent.

Validates artifact_draft dicts against the corresponding Pydantic create schemas.
Returns a list of human-readable error strings (empty = valid).
"""
from typing import Any

from pydantic import ValidationError

from core.schemas.registry import (
    AgentDefinitionCreate,
    McpServerCreate,
    SkillDefinitionCreate,
    ToolDefinitionCreate,
)

_ALLOWED_HANDLER_PREFIXES = (
    "tools.", "agents.", "skills.", "mcp.", "gateway.",
)

_SCHEMA_MAP: dict[str, type] = {
    "agent": AgentDefinitionCreate,
    "tool": ToolDefinitionCreate,
    "skill": SkillDefinitionCreate,
    "mcp_server": McpServerCreate,
}


def validate_artifact_draft(
    artifact_type: str, draft: dict[str, Any]
) -> list[str]:
    """Validate an artifact draft against its Pydantic schema.

    Returns a list of human-readable error strings. Empty list = valid.
    Also checks handler_module prefix is in the allowed list.
    """
    schema_cls = _SCHEMA_MAP.get(artifact_type)
    if schema_cls is None:
        return [f"Unknown artifact type: '{artifact_type}'. Valid: {list(_SCHEMA_MAP.keys())}"]

    errors: list[str] = []

    try:
        schema_cls.model_validate(draft)
    except ValidationError as exc:
        for err in exc.errors():
            field = " -> ".join(str(loc) for loc in err["loc"]) if err["loc"] else "root"
            errors.append(f"{field}: {err['msg']}")
    except Exception as exc:
        errors.append(f"Validation error: {exc}")

    handler_module = draft.get("handler_module")
    if handler_module and not handler_module.startswith(_ALLOWED_HANDLER_PREFIXES):
        errors.append(
            f"handler_module '{handler_module}' must start with one of: "
            f"{', '.join(_ALLOWED_HANDLER_PREFIXES)}"
        )

    return errors
