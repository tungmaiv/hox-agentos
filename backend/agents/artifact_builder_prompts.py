"""
System prompts for the artifact builder LangGraph agent.

Each artifact type has a detailed prompt that tells the LLM:
- What fields to collect and their types/constraints
- What questions to ask the admin
- How to format the artifact_draft JSON
- Validation rules to follow

Prompts are loaded from backend/prompts/artifact_builder_*.md via PromptLoader.
Edit the .md files directly to change prompt behavior — no Python change required.
"""
from core.prompts import load_prompt


def get_gather_type_prompt() -> str:
    """Return the system prompt for the gather_type node."""
    return load_prompt("artifact_builder_gather_type")


def get_system_prompt(artifact_type: str) -> str:
    """Return the system prompt for a specific artifact type.

    Loads from backend/prompts/artifact_builder_{artifact_type}.md.

    Raises FileNotFoundError if artifact_type is not recognized (i.e., no matching
    .md file exists). This is equivalent to the previous KeyError behavior — both
    are fatal programming errors, not runtime errors.
    """
    return load_prompt(f"artifact_builder_{artifact_type}")
