"""
Sandboxed condition expression evaluator for workflow condition_nodes.

Supported expression forms (all must start with "output."):
  output.field > 0              — numeric/boolean comparison
  output.field < 10
  output.field == true
  output.field == 'string'
  output.field != 'error'
  output.contains('keyword')   — substring check against output (stringified if dict)
  output.is_empty               — True if output is None, [], {}, or ""

Security: Only expressions matching _SAFE_PATTERN are accepted.
No eval(), exec(), or arbitrary attribute access chains.
"""
import re
from typing import Any

# Matches exactly three forms:
#   output.<field> <op> <value>
#   output.contains('<str>')
#   output.is_empty
_SAFE_PATTERN = re.compile(
    r"""^output\.(?:
        (\w+)\s*(>|<|==|!=)\s*(.+)   # field OP value
        |contains\('([^']+)'\)        # contains('keyword')
        |is_empty                     # is_empty
    )$""",
    re.VERBOSE,
)

_TRUE_LITERALS = {"true", "True", "1"}
_FALSE_LITERALS = {"false", "False", "0", "None", "null"}


def evaluate_condition(expression: str, output: Any) -> bool:
    """
    Evaluate a sandboxed condition expression against a node's output.

    Args:
        expression: A string matching one of the supported forms above.
        output:     The previous node's output (dict, list, str, int, bool, None).

    Returns:
        True or False.

    Raises:
        ValueError: If the expression does not match a supported form.
    """
    expr = expression.strip()
    match = _SAFE_PATTERN.match(expr)
    if match is None:
        raise ValueError(
            f"Unsupported expression: {expression!r}. "
            "Supported forms: output.field OP value, output.contains('str'), output.is_empty"
        )

    field: str | None = match.group(1)
    op: str | None = match.group(2)
    raw_value: str | None = match.group(3)
    contains_str: str | None = match.group(4)
    is_empty: bool = expr.endswith("is_empty")

    # ── is_empty ──────────────────────────────────────────────────────────────
    if is_empty:
        if output is None:
            return True
        if isinstance(output, (list, dict, str)):
            return len(output) == 0
        return False

    # ── contains ──────────────────────────────────────────────────────────────
    if contains_str is not None:
        text = output if isinstance(output, str) else str(output)
        return contains_str in text

    # ── field comparison ──────────────────────────────────────────────────────
    # Extract field value from output
    if isinstance(output, dict):
        actual = output.get(field)
    else:
        actual = getattr(output, field, None)

    # Parse right-hand side
    rhs_str = raw_value.strip()
    if rhs_str in _TRUE_LITERALS:
        rhs: Any = True
    elif rhs_str in _FALSE_LITERALS:
        rhs = False
    elif rhs_str.startswith("'") and rhs_str.endswith("'"):
        rhs = rhs_str[1:-1]
    else:
        try:
            rhs = int(rhs_str)
        except ValueError:
            try:
                rhs = float(rhs_str)
            except ValueError:
                raise ValueError(f"Cannot parse right-hand side value: {rhs_str!r}")

    if op == ">":
        return actual > rhs
    if op == "<":
        return actual < rhs
    if op == "==":
        return actual == rhs
    if op == "!=":
        return actual != rhs

    raise ValueError(f"Unsupported operator: {op!r}")
