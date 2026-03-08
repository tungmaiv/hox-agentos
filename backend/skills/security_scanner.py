"""
SecurityScanner -- computes trust scores for imported skills.

Scoring factors (weighted, summing to 100%):
- Source reputation (25%): known trusted domains vs unknown
- Tool scope (20%): read-only vs write vs sandbox vs admin
- Prompt safety (20%): scans for known prompt injection patterns
- Complexity (5%): step count
- Dependency risk (20%): undeclared/dangerous third-party imports in scripts
- Data flow risk (10%): sensitive-read + outbound-write pattern, credential leakage

Prompt injection patterns are checked against instruction_markdown and
all prompt_template fields in procedure steps.
"""
import ast
import re
import sys
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

# Stdlib module names (Python 3.10+)
_STDLIB_MODULES: frozenset[str] = sys.stdlib_module_names  # type: ignore[attr-defined]

# Packages considered dangerous for skill sandboxing
_DANGEROUS_PACKAGES: frozenset[str] = frozenset(
    {"requests", "httpx", "paramiko", "cryptography", "pycryptodome", "scapy", "nmap"}
)

# Tool names that write data outside the system (potential exfiltration sinks)
_OUTBOUND_TOOLS: frozenset[str] = frozenset({"http.post", "sandbox.run"})

# Tool names that read sensitive data (potential exfiltration sources)
_SENSITIVE_READ_TOOLS: frozenset[str] = frozenset(
    {"email.fetch", "crm.get", "crm.list", "calendar.list"}
)

# Credential leak patterns in prompt templates
_CREDENTIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"api.?key", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
]


@dataclass
class SecurityReport:
    """Result of a security scan on a skill."""

    score: int  # 0-100 overall score
    factors: dict[str, int]  # factor_name -> individual score (0-100)
    recommendation: str  # "approve", "review", "reject"
    injection_matches: list[str] = field(default_factory=list)


def _extract_imports_from_source(source: str) -> set[str]:
    """Parse Python source and extract top-level module names from import statements.

    Returns a set of top-level module names (e.g. "os.path" -> "os").
    On SyntaxError returns {"<unparseable>"} to signal the script is unsafe.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"<unparseable>"}

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Take the top-level package name
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


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
                instruction_markdown, scripts_content, declared_dependencies, etc.)
            source_url: URL the skill was imported from (if any).

        Returns:
            SecurityReport with score, factors, and recommendation.
            Factors: source_reputation(25%), tool_scope(20%), prompt_safety(20%),
                     complexity(5%), dependency_risk(20%), data_flow_risk(10%).
        """
        factors: dict[str, int] = {}

        # Factor 1: Source reputation (25%)
        factors["source_reputation"] = self._score_source(source_url)

        # Factor 2: Tool scope (20%)
        factors["tool_scope"] = self._score_tool_scope(skill_data)

        # Factor 3: Prompt safety (20%)
        prompt_score, matches = self._score_prompt_safety(skill_data)
        factors["prompt_safety"] = prompt_score

        # Factor 4: Complexity (5%)
        factors["complexity"] = self._score_complexity(skill_data)

        # Factor 5: Dependency risk (20%)
        factors["dependency_risk"] = self._score_dependency_risk(skill_data)

        # Factor 6: Data flow risk (10%)
        factors["data_flow_risk"] = self._score_data_flow_risk(skill_data)

        # Compute weighted overall score (weights sum to 1.00)
        overall = (
            factors["source_reputation"] * 0.25
            + factors["tool_scope"] * 0.20
            + factors["prompt_safety"] * 0.20
            + factors["complexity"] * 0.05
            + factors["dependency_risk"] * 0.20
            + factors["data_flow_risk"] * 0.10
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

    def _score_dependency_risk(self, skill_data: dict[str, Any]) -> int:
        """Score based on third-party dependencies in attached scripts.

        Returns:
            0   — undeclared third-party imports detected (untrusted execution risk)
            <100 — declared but dangerous packages found (penalty per package)
            100  — no scripts, or all imports are stdlib/declared/safe
        """
        scripts_content: list[dict[str, str]] = skill_data.get("scripts_content", [])
        if not scripts_content:
            return 100

        # Collect all imports across all scripts
        all_imports: set[str] = set()
        for script in scripts_content:
            source = script.get("source", "")
            if source:
                all_imports |= _extract_imports_from_source(source)

        # Third-party = all imports minus stdlib
        third_party_imports = all_imports - _STDLIB_MODULES

        # Signal 3: undeclared imports -> immediate rejection
        declared_set: set[str] = set(skill_data.get("declared_dependencies", []))
        undeclared = third_party_imports - declared_set
        if undeclared:
            return 0

        # Signal 1: dangerous packages declared
        dangerous_found = declared_set & _DANGEROUS_PACKAGES
        danger_penalty = len(dangerous_found) * 20

        # Signal 2: bloat score by dependency count
        dep_count = len(declared_set)
        if dep_count == 0:
            bloat_score = 100
        elif dep_count <= 3:
            bloat_score = 80
        elif dep_count <= 10:
            bloat_score = 50
        else:
            bloat_score = 20

        return max(0, bloat_score - danger_penalty)

    def _score_data_flow_risk(self, skill_data: dict[str, Any]) -> int:
        """Score based on data flow patterns that indicate exfiltration risk.

        Returns:
            100  — no procedure, or clean data flow
            <100 — sensitive-read + outbound-write detected, or credential patterns found
        """
        procedure = skill_data.get("procedure_json")
        if not procedure:
            return 100

        steps = procedure.get("steps", [])
        tool_names: list[str] = []
        prompt_templates: list[str] = []

        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("type") == "tool":
                tool_name = step.get("tool", "")
                if tool_name:
                    tool_names.append(tool_name)
            prompt = step.get("prompt_template", "")
            if prompt:
                prompt_templates.append(prompt)

        score = 100

        # Signal 1: exfiltration pattern — sensitive read + outbound write
        has_sensitive_read = any(t in _SENSITIVE_READ_TOOLS for t in tool_names)
        has_outbound = any(t in _OUTBOUND_TOOLS for t in tool_names)
        if has_sensitive_read and has_outbound:
            score -= 60

        # Signal 2: credential patterns in prompt templates
        combined_prompts = "\n".join(prompt_templates)
        for pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(combined_prompts):
                score -= 30
                break  # count once only

        # Signal 3: admin or sandbox tools in the procedure
        for tool_name in tool_names:
            scope = self._classify_tool_scope(tool_name)
            if scope == 0:  # admin
                score -= 40
                break
            elif scope <= 30:  # sandbox
                score -= 20
                break

        return max(0, score)
