"""
SecurityScanner -- computes trust scores for imported skills.

Scoring factors (weighted):
- Source reputation (30%): known trusted domains vs unknown
- Tool scope (25%): read-only vs write vs sandbox vs admin
- Prompt safety (25%): scans for known prompt injection patterns
- Complexity (10%): step count
- Author verification (10%): signed vs unsigned (MVP: always unsigned)

Prompt injection patterns are checked against instruction_markdown and
all prompt_template fields in procedure steps.
"""
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)

# Known prompt injection patterns -- matched case-insensitively
INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(everything|all|your)",
    r"you\s+are\s+now\s+a",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"Human:\s*|Assistant:\s*",
    r"(curl|wget|fetch)\s+http",
    r"base64\.(encode|decode)",
    r"eval\(|exec\(|__import__",
]

# Compiled patterns for efficiency
_COMPILED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS
]

# Trusted source domains
_TRUSTED_SOURCES: set[str] = {
    "agentskills.io",
    "github.com/blitz-agentos",
    "skills.blitz.local",
}

# Tool scope classification: tool name prefix -> scope level
# Higher is more dangerous
_TOOL_SCOPE_SCORES: dict[str, int] = {
    "read": 100,
    "email.fetch": 100,
    "calendar.list": 100,
    "crm.get": 100,
    "crm.list": 100,
    "write": 60,
    "email.send": 60,
    "calendar.create": 60,
    "crm.update": 60,
    "sandbox": 30,
    "admin": 0,
}


@dataclass
class SecurityReport:
    """Result of a security scan on a skill."""

    score: int  # 0-100 overall score
    factors: dict[str, int]  # factor_name -> individual score (0-100)
    recommendation: str  # "approve", "review", "reject"
    injection_matches: list[str] = field(default_factory=list)


class SecurityScanner:
    """Scans imported skills for security risks and computes trust scores."""

    def scan(
        self,
        skill_data: dict[str, Any],
        source_url: str | None = None,
    ) -> SecurityReport:
        """Scan a skill and compute a trust score.

        Args:
            skill_data: Parsed skill data dict (name, procedure_json,
                instruction_markdown, etc.)
            source_url: URL the skill was imported from (if any).

        Returns:
            SecurityReport with score, factors, and recommendation.
        """
        factors: dict[str, int] = {}

        # Factor 1: Source reputation (30%)
        factors["source_reputation"] = self._score_source(source_url)

        # Factor 2: Tool scope (25%)
        factors["tool_scope"] = self._score_tool_scope(skill_data)

        # Factor 3: Prompt safety (25%)
        prompt_score, matches = self._score_prompt_safety(skill_data)
        factors["prompt_safety"] = prompt_score

        # Factor 4: Complexity (10%)
        factors["complexity"] = self._score_complexity(skill_data)

        # Factor 5: Author verification (10%)
        factors["author_verification"] = self._score_author_verification(
            skill_data
        )

        # Compute weighted overall score
        overall = (
            factors["source_reputation"] * 0.30
            + factors["tool_scope"] * 0.25
            + factors["prompt_safety"] * 0.25
            + factors["complexity"] * 0.10
            + factors["author_verification"] * 0.10
        )
        score = int(round(overall))

        # Determine recommendation
        if score >= 80:
            recommendation = "approve"
        elif score >= 60:
            recommendation = "review"
        else:
            recommendation = "reject"

        logger.info(
            "security_scan_complete",
            skill_name=skill_data.get("name"),
            score=score,
            recommendation=recommendation,
            injection_matches=len(matches),
        )

        return SecurityReport(
            score=score,
            factors=factors,
            recommendation=recommendation,
            injection_matches=matches,
        )

    def _score_source(self, source_url: str | None) -> int:
        """Score based on source URL reputation.

        Uses proper URL parsing to prevent bypass via query string tricks
        (e.g., "https://evil.com?redirect=agentskills.io").
        """
        if source_url is None:
            # Manual paste / direct creation
            return 40

        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""
        # Match hostname or hostname + path prefix for GitHub-style sources
        full_host_path = f"{hostname}{parsed.path}"
        for trusted in _TRUSTED_SOURCES:
            if hostname == trusted or hostname.endswith(f".{trusted}"):
                return 95
            # Handle path-based sources like "github.com/blitz-agentos"
            if "/" in trusted and full_host_path.startswith(trusted):
                return 95

        # Unknown URL
        return 20

    def _score_tool_scope(self, skill_data: dict[str, Any]) -> int:
        """Score based on tools referenced in the skill."""
        procedure = skill_data.get("procedure_json")
        if not procedure:
            # Instructional skill -- no tool calls
            return 100

        steps = procedure.get("steps", [])
        tool_steps = [s for s in steps if isinstance(s, dict) and s.get("type") == "tool"]

        if not tool_steps:
            return 100

        scores: list[int] = []
        for step in tool_steps:
            tool_name = step.get("tool", "")
            score = self._classify_tool_scope(tool_name)
            scores.append(score)

        return int(round(sum(scores) / len(scores)))

    def _classify_tool_scope(self, tool_name: str) -> int:
        """Classify a single tool name by scope risk."""
        # Exact match first
        if tool_name in _TOOL_SCOPE_SCORES:
            return _TOOL_SCOPE_SCORES[tool_name]

        # Prefix matching
        lower = tool_name.lower()
        if "admin" in lower:
            return 0
        if "sandbox" in lower:
            return 30
        if any(w in lower for w in ("send", "create", "update", "delete", "write")):
            return 60
        if any(w in lower for w in ("fetch", "get", "list", "read", "search")):
            return 100

        # Unknown tool -- moderate risk
        return 50

    def _score_prompt_safety(
        self, skill_data: dict[str, Any]
    ) -> tuple[int, list[str]]:
        """Scan all text content for prompt injection patterns."""
        texts_to_scan: list[str] = []

        # Instruction markdown
        instruction = skill_data.get("instruction_markdown", "")
        if instruction:
            texts_to_scan.append(instruction)

        # Prompt templates in procedure steps
        procedure = skill_data.get("procedure_json")
        if procedure:
            for step in procedure.get("steps", []):
                if isinstance(step, dict):
                    prompt = step.get("prompt_template", "")
                    if prompt:
                        texts_to_scan.append(prompt)

        combined_text = "\n".join(texts_to_scan)
        matches: list[str] = []

        for pattern in _COMPILED_PATTERNS:
            found = pattern.findall(combined_text)
            if found:
                matches.extend(found)

        if not matches:
            return 100, []

        # Each match reduces score by 50, floor at 0
        score = max(0, 100 - len(matches) * 50)
        return score, matches

    def _score_complexity(self, skill_data: dict[str, Any]) -> int:
        """Score based on step count."""
        procedure = skill_data.get("procedure_json")
        if not procedure:
            return 100  # instructional skills are simple

        step_count = len(procedure.get("steps", []))
        if step_count <= 5:
            return 100
        elif step_count <= 10:
            return 70
        elif step_count <= 20:
            return 40
        return 20  # over 20 steps

    def _score_author_verification(self, skill_data: dict[str, Any]) -> int:
        """Score based on author verification status.

        MVP: always unsigned = 50. Signed verification deferred.
        """
        # MVP: no signature verification implemented yet
        return 50
