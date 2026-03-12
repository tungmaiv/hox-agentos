"""
SkillExecutor -- runs procedural skill pipelines step-by-step.

Execution flow:
1. Iterate through procedure_json["steps"] sequentially
2. For each step:
   - tool: get_tool() + check_tool_acl() + invoke handler
   - llm: get_llm() + resolve prompt template + invoke LLM
   - condition: safe_eval_condition() + route to true/false step
3. Emit AG-UI step_progress events via event_emitter callback
4. Return SkillResult with outputs and optional error info

Security:
- Tool steps pass through 3-gate security (get_tool verifies active, check_tool_acl for Gate 3)
- LLM steps use get_llm() (single entry point for all LLM access)
- Condition steps use AST-based safe_eval_condition (no eval())
"""
import importlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_llm
from core.logging import get_audit_logger
from registry.service import get_tool
from security.acl import check_tool_acl
from skills.safe_eval import safe_eval_condition

logger = structlog.get_logger(__name__)
audit_logger = get_audit_logger()

# Allowed module prefixes for tool handler dispatch via importlib.
# Prevents a compromised admin from pointing a tool_definition at arbitrary
# Python modules (e.g., os, subprocess). Only modules under these prefixes
# can be loaded for tool execution.
_ALLOWED_HANDLER_PREFIXES: tuple[str, ...] = (
    "tools.",
    "agents.",
    "skills.",
    "mcp.",
    "gateway.",
)


class SkillStepError(Exception):
    """Raised when a skill step fails (ACL denied, tool not found, etc.)."""


@dataclass
class StepContext:
    """Execution context passed between steps."""

    user_input: dict[str, Any] | None
    outputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillResult:
    """Result of executing a procedural skill."""

    success: bool
    output: str
    step_outputs: dict[str, Any] = field(default_factory=dict)
    failed_step: str | None = None


class SkillExecutor:
    """Runs procedural skill pipelines with 3-gate security and AG-UI streaming."""

    async def run(
        self,
        skill: Any,  # SkillDefinition ORM object
        user_context: dict[str, Any],
        session: AsyncSession,
        user_input: dict[str, Any] | None = None,
        event_emitter: Callable[..., Any] | None = None,
    ) -> SkillResult:
        """Execute a procedural skill pipeline.

        Args:
            skill: SkillDefinition with procedure_json.
            user_context: UserContext dict from JWT (user_id, roles, etc.).
            session: Async DB session for tool registry/ACL lookups.
            user_input: Optional user-provided input parameters.
            event_emitter: Optional callback for AG-UI step_progress events.

        Returns:
            SkillResult with success status, output, and step outputs.
        """
        procedure = skill.procedure_json
        if not procedure or "steps" not in procedure:
            return SkillResult(
                success=False,
                output="Invalid skill: missing procedure_json or steps",
            )

        steps = procedure["steps"]
        context = StepContext(user_input=user_input)
        user_id: UUID = user_context["user_id"]

        # Capture skill metadata for audit logging in _run_tool_step()
        self._current_skill_name = getattr(skill, "name", "unknown")
        self._current_skill_id = getattr(skill, "id", None)

        # Read allowed_tools from ORM model (None or empty list = permissive)
        skill_allowed_tools: list[str] | None = getattr(skill, "allowed_tools", None)

        # Build step index for condition routing
        step_index: dict[str, int] = {}
        for i, step in enumerate(steps):
            step_index[step["id"]] = i

        i = 0
        while i < len(steps):
            step = steps[i]
            step_id = step["id"]
            step_type = step["type"]
            start_ms = time.monotonic()

            try:
                if step_type == "tool":
                    result = await self._run_tool_step(
                        step, context, user_id, session,
                        allowed_tools=skill_allowed_tools,
                    )
                    context.outputs[step_id] = result
                elif step_type == "llm":
                    result = await self._run_llm_step(step, context)
                    context.outputs[step_id] = result
                elif step_type == "condition":
                    branch_target = await self._run_condition_step(
                        step, context
                    )
                    context.outputs[step_id] = branch_target is not None
                    # Route to target step
                    if branch_target and branch_target in step_index:
                        i = step_index[branch_target]
                        # Emit event for condition step before jumping
                        duration_ms = int((time.monotonic() - start_ms) * 1000)
                        await self._emit_step_event(
                            event_emitter, skill.name, step, "completed",
                            duration_ms,
                        )
                        logger.info(
                            "skill_step_completed",
                            skill_name=skill.name,
                            step_id=step_id,
                            step_type=step_type,
                            user_id=str(user_id),
                            duration_ms=duration_ms,
                        )
                        continue
                else:
                    raise SkillStepError(f"Unknown step type: {step_type}")

                duration_ms = int((time.monotonic() - start_ms) * 1000)

                # Emit AG-UI step_progress event
                await self._emit_step_event(
                    event_emitter, skill.name, step, "completed", duration_ms,
                )

                # Audit log
                logger.info(
                    "skill_step_completed",
                    skill_name=skill.name,
                    step_id=step_id,
                    step_type=step_type,
                    tool_name=step.get("tool"),
                    user_id=str(user_id),
                    duration_ms=duration_ms,
                )

            except Exception as exc:
                duration_ms = int((time.monotonic() - start_ms) * 1000)

                # Emit failed event
                await self._emit_step_event(
                    event_emitter, skill.name, step, "failed", duration_ms,
                )

                logger.error(
                    "skill_step_failed",
                    skill_name=skill.name,
                    step_id=step_id,
                    step_type=step_type,
                    error=str(exc),
                    user_id=str(user_id),
                    duration_ms=duration_ms,
                )

                return SkillResult(
                    success=False,
                    output=str(exc),
                    step_outputs=dict(context.outputs),
                    failed_step=step_id,
                )

            i += 1

        # Build output from template or last step
        output = self._build_output(procedure, context)
        return SkillResult(
            success=True,
            output=output,
            step_outputs=dict(context.outputs),
        )

    async def _run_tool_step(
        self,
        step: dict[str, Any],
        context: StepContext,
        user_id: UUID,
        session: AsyncSession,
        allowed_tools: list[str] | None = None,
    ) -> Any:
        """Execute a tool step with allowed_tools pre-gate + 3-gate security."""
        tool_name = step["tool"]

        # Skill-declared allowed_tools pre-gate (SKSEC-02).
        # None or empty list = permissive (backwards-compatible with existing skills).
        # Fires BEFORE get_tool() — no DB lookup on denied calls.
        if allowed_tools is not None and len(allowed_tools) > 0:
            if tool_name not in allowed_tools:
                audit_logger.info(
                    "skill_allowed_tools_denied",
                    skill_name=getattr(self, "_current_skill_name", "unknown"),
                    skill_id=getattr(self, "_current_skill_id", None),
                    tool_name=tool_name,
                    user_id=str(user_id),
                    declared_allowed_tools=allowed_tools,
                )
                raise SkillStepError(
                    f"Tool '{tool_name}' not permitted by this skill. "
                    f"Declared allowed tools: {allowed_tools}"
                )

        # Gate: verify tool exists and is active
        tool_def = await get_tool(tool_name, session)
        if tool_def is None:
            raise SkillStepError(f"Tool '{tool_name}' not found or not active")

        # Gate 3: Tool ACL check
        allowed = await check_tool_acl(user_id, tool_name, session)
        if not allowed:
            raise SkillStepError(
                f"Access denied: user not authorized for tool '{tool_name}'"
            )

        # Resolve params with variable interpolation
        params = step.get("params", {})
        resolved_params = {}
        for key, value in params.items():
            if isinstance(value, str):
                resolved_params[key] = self._resolve_template(value, context)
            else:
                resolved_params[key] = value

        # Invoke the tool handler
        handler_module = tool_def.get("handler_module")
        handler_function = tool_def.get("handler_function")
        if not handler_module or not handler_function:
            raise SkillStepError(
                f"Tool '{tool_name}' has no handler configured"
            )

        # Validate handler_module against allowed prefixes to prevent
        # arbitrary module loading (e.g., os, subprocess, shutil).
        if not handler_module.startswith(_ALLOWED_HANDLER_PREFIXES):
            raise SkillStepError(
                f"Tool '{tool_name}' handler module '{handler_module}' "
                f"is outside allowed prefixes: {_ALLOWED_HANDLER_PREFIXES}"
            )

        module = importlib.import_module(handler_module)
        handler = getattr(module, handler_function)
        result = await handler(**resolved_params)
        return result

    async def _run_llm_step(
        self,
        step: dict[str, Any],
        context: StepContext,
    ) -> str:
        """Execute an LLM step using get_llm()."""
        model_alias = step["model_alias"]
        prompt_template = step["prompt_template"]

        # Resolve template variables
        prompt = self._resolve_template(prompt_template, context)

        # Get LLM via single entry point
        llm = get_llm(model_alias)
        response = await llm.ainvoke(prompt)

        # Extract text content from response
        if hasattr(response, "content"):
            return str(response.content)
        return str(response)

    async def _run_condition_step(
        self,
        step: dict[str, Any],
        context: StepContext,
    ) -> str | None:
        """Evaluate condition and return target step ID (or None for next)."""
        expression = step["expression"]

        # Resolve template variables in expression
        resolved_expr = self._resolve_template(expression, context)

        # Evaluate using AST-based safe evaluator (NO eval())
        result = safe_eval_condition(resolved_expr, context.outputs)

        if result:
            return step.get("true_step")
        return step.get("false_step")

    def _resolve_template(self, template: str, context: StepContext) -> str:
        """Replace {{step_id.output}} with actual values from context."""
        import re

        def replacer(match: re.Match[str]) -> str:
            step_id = match.group(1)
            value = context.outputs.get(step_id, "")
            return str(value)

        return re.sub(r"\{\{(\w+)\.output\}\}", replacer, template)

    def _build_output(
        self, procedure: dict[str, Any], context: StepContext
    ) -> str:
        """Build final output from output template or last step output."""
        output_template = procedure.get("output")
        if output_template and isinstance(output_template, str):
            return self._resolve_template(output_template, context)

        # Default: return last step output
        if context.outputs:
            last_key = list(context.outputs.keys())[-1]
            return str(context.outputs[last_key])
        return ""

    async def _emit_step_event(
        self,
        event_emitter: Callable[..., Any] | None,
        skill_name: str,
        step: dict[str, Any],
        status: str,
        duration_ms: int,
    ) -> None:
        """Emit AG-UI step_progress event if emitter is provided."""
        if event_emitter is None:
            return
        await event_emitter({
            "type": "step_progress",
            "skill_name": skill_name,
            "step_id": step["id"],
            "step_type": step["type"],
            "status": status,
            "description": step.get("description", ""),
            "duration_ms": duration_ms,
        })
