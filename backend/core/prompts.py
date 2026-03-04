# backend/core/prompts.py
"""
PromptLoader — load and cache LLM instruction text from backend/prompts/*.md files.

Usage:
    from core.prompts import load_prompt

    # No substitution
    system = load_prompt("master_agent")

    # With Jinja2-style {{ var }} substitution
    prompt = load_prompt("master_agent")  # see backend/prompts/*.md for available prompts

Dev mode (ENVIRONMENT=development): bypasses cache so .md edits are visible without restart.
Production/test mode: caches raw template in-process after first read.
"""
import os
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Module-level in-memory cache: maps prompt name -> raw template string.
# Populated on first access per name. In development mode the cache is bypassed.
_cache: dict[str, str] = {}


def _prompts_dir() -> Path:
    """Return the absolute path to backend/prompts/ regardless of cwd."""
    # __file__ is backend/core/prompts.py — parent is backend/core/, parent.parent is backend/
    return Path(__file__).parent.parent / "prompts"


def load_prompt(prompt_name: str, **vars: str) -> str:
    """
    Load a prompt template from backend/prompts/{prompt_name}.md and return the rendered string.

    Args:
        prompt_name: Prompt file name without the .md extension (e.g. "master_agent").
        **vars: Variable substitutions applied to Jinja2-style {{ var_name }} placeholders.
                The keyword argument names must match the placeholder names in the template.

    Returns:
        The prompt text with all {{ key }} placeholders replaced by the corresponding values.

    Raises:
        FileNotFoundError: If the .md file does not exist at the expected path.

    Example:
        load_prompt("master_agent")
        load_prompt("artifact_builder", context="my api spec")  # see backend/prompts/*.md for available prompts
        load_prompt("_test_probe", name="World")  # name= is a valid var here
    """
    env = os.getenv("ENVIRONMENT", "production")
    dev_mode = env == "development"

    if not dev_mode and prompt_name in _cache:
        raw = _cache[prompt_name]
    else:
        prompt_path = _prompts_dir() / f"{prompt_name}.md"
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}. "
                f"Expected a .md file at backend/prompts/{prompt_name}.md"
            )
        raw = prompt_path.read_text(encoding="utf-8")
        logger.debug("prompt_loaded_from_disk", name=prompt_name, path=str(prompt_path))

        if not dev_mode:
            _cache[prompt_name] = raw

    # Apply Jinja2-style {{ var_name }} substitutions
    rendered = raw
    for key, value in vars.items():
        rendered = rendered.replace("{{ " + key + " }}", value)

    return rendered


def clear_cache() -> None:
    """Clear the in-memory prompt cache. Used for test isolation."""
    _cache.clear()
