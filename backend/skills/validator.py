"""
SkillValidator -- validates procedure_json for procedural skills.

Validation rules:
- schema_version must be present and equal to "1.0"
- steps must be a non-empty list, length <= 20
- Each step has unique id and valid type (tool, llm, condition)
- tool steps require 'tool' field
- llm steps require 'model_alias' and 'prompt_template'
- condition steps require 'expression' and 'true_step'
- Variable refs {{step_id.output}} must reference prior step IDs
- No circular references in condition routing
- Prompt template size <= 10KB per step
- Condition expressions must be parseable by safe_eval_condition
"""
import ast
import re
from typing import Any

# Pattern to extract {{step_id.output}} references
_VAR_REF_RE = re.compile(r"\{\{(\w+)\.output\}\}")

_VALID_STEP_TYPES = {"tool", "llm", "condition"}
_MAX_STEPS = 20
_MAX_PROMPT_SIZE = 10 * 1024  # 10KB


class SkillValidator:
    """Validates procedure_json for procedural skills."""

    def validate_procedure(self, procedure_json: dict[str, Any]) -> list[str]:
        """Validate a procedure_json structure.

        Args:
            procedure_json: The procedure definition to validate.

        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []

        # schema_version check
        schema_version = procedure_json.get("schema_version")
        if schema_version is None:
            errors.append("schema_version is required")
        elif schema_version != "1.0":
            errors.append(f"schema_version must be '1.0', got '{schema_version}'")

        # steps check
        steps = procedure_json.get("steps")
        if steps is None:
            errors.append("steps is required")
            return errors
        if not isinstance(steps, list):
            errors.append("steps must be a list")
            return errors
        if len(steps) == 0:
            errors.append("steps must not be empty")
            return errors
        if len(steps) > _MAX_STEPS:
            errors.append(f"steps count {len(steps)} exceeds maximum of {_MAX_STEPS}")

        # Collect step IDs for forward-reference checking
        step_ids: list[str] = []
        seen_ids: set[str] = set()

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"step[{i}] must be a dict")
                continue

            # id check
            step_id = step.get("id")
            if step_id is None:
                errors.append(f"step[{i}] missing 'id'")
            else:
                if step_id in seen_ids:
                    errors.append(f"step[{i}] duplicate id '{step_id}'")
                seen_ids.add(step_id)
                step_ids.append(step_id)

            # type check
            step_type = step.get("type")
            if step_type is None:
                errors.append(f"step[{i}] missing 'type'")
            elif step_type not in _VALID_STEP_TYPES:
                errors.append(
                    f"step[{i}] invalid type '{step_type}' "
                    f"(must be one of: {', '.join(sorted(_VALID_STEP_TYPES))})"
                )
            else:
                # Type-specific validation
                errors.extend(self._validate_step_fields(i, step, step_type))

        # Validate variable references point to prior steps
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            prior_ids = set(step_ids[:i])
            errors.extend(self._validate_var_refs(i, step, prior_ids))

        # Validate condition step routing (no cycles, targets exist)
        errors.extend(self._validate_condition_routing(steps, step_ids))

        # Validate output template references
        output_template = procedure_json.get("output")
        if output_template and isinstance(output_template, str):
            refs = _VAR_REF_RE.findall(output_template)
            all_ids = set(step_ids)
            for ref in refs:
                if ref not in all_ids:
                    errors.append(
                        f"output template references unknown step '{ref}'"
                    )

        return errors

    def _validate_step_fields(
        self, index: int, step: dict[str, Any], step_type: str
    ) -> list[str]:
        """Validate type-specific required fields."""
        errors: list[str] = []

        if step_type == "tool":
            if not step.get("tool"):
                errors.append(f"step[{index}] tool step requires 'tool' field")

        elif step_type == "llm":
            if not step.get("model_alias"):
                errors.append(
                    f"step[{index}] llm step requires 'model_alias' field"
                )
            prompt = step.get("prompt_template")
            if not prompt:
                errors.append(
                    f"step[{index}] llm step requires 'prompt_template' field"
                )
            elif isinstance(prompt, str) and len(prompt) > _MAX_PROMPT_SIZE:
                errors.append(
                    f"step[{index}] prompt_template exceeds {_MAX_PROMPT_SIZE} bytes"
                )

        elif step_type == "condition":
            expression = step.get("expression")
            if not expression:
                errors.append(
                    f"step[{index}] condition step requires 'expression' field"
                )
            else:
                # Dry-run AST parse to check expression structure safety.
                # We only check that the AST nodes are safe (no imports, no
                # attribute access, no eval/exec calls). We do NOT evaluate
                # -- so unknown variables are fine at validation time.
                errors.extend(self._check_expression_safety(index, expression))
            if not step.get("true_step"):
                errors.append(
                    f"step[{index}] condition step requires 'true_step' field"
                )

        return errors

    # Node types that are safe in condition expressions.
    # Anything not in this set is rejected.
    _SAFE_AST_NODES = frozenset({
        ast.Expression,
        ast.Compare,
        ast.BoolOp,
        ast.UnaryOp,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Gt,
        ast.GtE,
        ast.Lt,
        ast.LtE,
        ast.Eq,
        ast.NotEq,
        ast.Is,
        ast.IsNot,
        ast.Constant,
        ast.Name,
        ast.Load,
        ast.Call,
    })

    def _check_expression_safety(
        self, index: int, expression: str
    ) -> list[str]:
        """Check that a condition expression is structurally safe via AST.

        Only validates AST node types -- does NOT evaluate the expression.
        Unknown variables are allowed since they are resolved at runtime.
        """
        errors: list[str] = []

        # Resolve template vars to safe placeholder names for parsing
        resolved = re.sub(r"\{\{(\w+)\.output\}\}", r"_var_\1_output", expression)

        try:
            tree = ast.parse(resolved, mode="eval")
        except SyntaxError as exc:
            errors.append(
                f"step[{index}] condition expression has invalid syntax: {exc}"
            )
            return errors

        # Walk every node in the AST -- reject any node type not in safe set
        for node in ast.walk(tree):
            node_type = type(node)
            if node_type not in self._SAFE_AST_NODES:
                errors.append(
                    f"step[{index}] unsafe condition expression: "
                    f"{node_type.__name__} not allowed"
                )
                break  # one error is enough

            # Extra check: Call nodes must be len() only
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id != "len":
                    func_name = (
                        node.func.id
                        if isinstance(node.func, ast.Name)
                        else "unknown"
                    )
                    errors.append(
                        f"step[{index}] unsafe condition expression: "
                        f"{func_name}() not allowed (only len())"
                    )
                    break

        return errors

    def _validate_var_refs(
        self, index: int, step: dict[str, Any], prior_ids: set[str]
    ) -> list[str]:
        """Validate that {{step_id.output}} refs point to prior step IDs."""
        errors: list[str] = []

        # Check prompt_template in llm steps
        prompt = step.get("prompt_template", "")
        if isinstance(prompt, str):
            for ref in _VAR_REF_RE.findall(prompt):
                if ref not in prior_ids:
                    errors.append(
                        f"step[{index}] references unknown prior step '{ref}' "
                        f"in prompt_template"
                    )

        # Check params in tool steps
        params = step.get("params", {})
        if isinstance(params, dict):
            for key, value in params.items():
                if isinstance(value, str):
                    for ref in _VAR_REF_RE.findall(value):
                        if ref not in prior_ids:
                            errors.append(
                                f"step[{index}] references unknown prior step "
                                f"'{ref}' in params.{key}"
                            )

        return errors

    def _validate_condition_routing(
        self, steps: list[Any], step_ids: list[str]
    ) -> list[str]:
        """Validate condition step routing targets exist and no cycles."""
        errors: list[str] = []
        all_ids = set(step_ids)

        for i, step in enumerate(steps):
            if not isinstance(step, dict) or step.get("type") != "condition":
                continue

            true_step = step.get("true_step")
            if true_step and true_step not in all_ids:
                errors.append(
                    f"step[{i}] true_step '{true_step}' references unknown step"
                )

            false_step = step.get("false_step")
            if false_step and false_step not in all_ids:
                errors.append(
                    f"step[{i}] false_step '{false_step}' references unknown step"
                )

            # Check for backward jumps (potential cycles) -- MVP: conditions skip forward only
            step_id = step.get("id")
            if step_id:
                current_idx = step_ids.index(step_id) if step_id in step_ids else i
                if true_step and true_step in all_ids:
                    target_idx = step_ids.index(true_step)
                    if target_idx <= current_idx:
                        errors.append(
                            f"step[{i}] true_step '{true_step}' creates backward "
                            f"jump (potential cycle)"
                        )
                if false_step and false_step in all_ids:
                    target_idx = step_ids.index(false_step)
                    if target_idx <= current_idx:
                        errors.append(
                            f"step[{i}] false_step '{false_step}' creates backward "
                            f"jump (potential cycle)"
                        )

        return errors
