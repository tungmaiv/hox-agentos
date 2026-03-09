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
import json

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


def get_skill_generation_prompt(artifact_type: str, draft: dict) -> str:
    """Return the system prompt for the generate_skill_content node.

    Instructs the LLM to generate full, executable content for an artifact based
    on the name and description already collected in the draft.

    Output format varies by artifact_type:
    - "skill" + skill_type="procedural" → JSON code block containing procedure_json
      with steps (each step has: step, tool, prompt fields)
    - "skill" + skill_type="instructional" → Markdown starting with "# "
    - "tool" → Python code block with InputModel/OutputModel Pydantic classes
      and an async handler function

    Args:
        artifact_type: "skill" or "tool"
        draft: Current artifact draft dict (must have name and description)

    Returns:
        System prompt string for the LLM.
    """
    name = draft.get("name", "")
    description = draft.get("description", "")
    skill_type = draft.get("skill_type", "instructional")

    draft_context = f"Name: {name}\nDescription: {description}\n"

    if artifact_type == "tool":
        return (
            "You are an expert Python developer helping build tool handler stubs for the Blitz AgentOS platform.\n\n"
            f"Generate a Python handler stub for the following tool:\n{draft_context}\n"
            "Requirements:\n"
            "1. Define an `InputModel` class inheriting from `pydantic.BaseModel` with appropriate fields.\n"
            "2. Define an `OutputModel` class inheriting from `pydantic.BaseModel` with appropriate fields.\n"
            "3. Define an `async def handler(input: InputModel) -> OutputModel:` function.\n"
            "4. Include docstrings explaining what the tool does.\n"
            "5. Include `from pydantic import BaseModel` import at the top.\n"
            "Output ONLY a Python code block (```python ... ```). No explanation text."
        )

    if skill_type == "procedural":
        return (
            "You are an expert workflow designer helping build procedural skill definitions for the Blitz AgentOS platform.\n\n"
            f"Generate a complete procedure_json for the following skill:\n{draft_context}\n"
            "The procedure_json must be a JSON object with:\n"
            "- schema_version: '1.0'\n"
            "- steps: array of step objects, each with:\n"
            "  - step: integer (1, 2, 3...)\n"
            "  - tool: string (e.g. 'email.fetch', 'llm.summarize', 'calendar.list')\n"
            "  - prompt: string describing what this step does\n"
            "\nOutput a JSON code block containing the full object:\n"
            "```json\n"
            '{"procedure_json": {"schema_version": "1.0", "steps": [...]}}\n'
            "```\n"
            "Output ONLY the JSON code block. No explanation text."
        )

    # Default: instructional skill
    return (
        "You are an expert technical writer helping create skill instructions for the Blitz AgentOS platform.\n\n"
        f"Generate clear, detailed instructions for the following skill:\n{draft_context}\n"
        "Requirements:\n"
        "1. Start with a top-level heading: `# {name}`\n"
        "2. Include a brief overview paragraph.\n"
        "3. Add a `## Usage` section explaining how to trigger/use the skill.\n"
        "4. Add a `## What it does` section with step-by-step explanation.\n"
        "5. Keep the tone professional and concise.\n"
        "\nOutput ONLY the markdown content starting with `# `. No code blocks or preamble."
    )
