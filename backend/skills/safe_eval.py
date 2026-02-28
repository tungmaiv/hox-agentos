"""
AST-based safe expression evaluator for condition steps in procedural skills.

Supports ONLY:
- Comparisons: X > N, X < N, X >= N, X <= N, X == Y, X != Y
- Function calls: len(X) only -- all other functions rejected
- Variables: resolved from step output context
- Literals: integers, strings, booleans, None
- Boolean operators: and, or

NO eval(), NO exec(), NO arbitrary code execution.
"""
import ast
import re
from typing import Any


class UnsafeExpressionError(Exception):
    """Raised when an expression contains unsafe constructs."""


# Pattern to match {{step_id.output}} template variables
_TEMPLATE_VAR_RE = re.compile(r"\{\{(\w+)\.output\}\}")


def _resolve_template_vars(
    expression: str, variables: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Replace {{step_id.output}} with Python-safe variable names.

    Returns the rewritten expression and a variables dict mapping
    safe names to actual values.
    """
    safe_vars: dict[str, Any] = {}

    def replacer(match: re.Match[str]) -> str:
        step_id = match.group(1)
        safe_name = f"_var_{step_id}_output"
        safe_vars[safe_name] = variables.get(step_id)
        return safe_name

    resolved = _TEMPLATE_VAR_RE.sub(replacer, expression)

    # Also add plain variable names from the variables dict
    for key, value in variables.items():
        if key not in safe_vars:
            safe_vars[key] = value

    return resolved, safe_vars


class _SafeEvaluator(ast.NodeVisitor):
    """AST visitor that evaluates only safe expression constructs."""

    def __init__(self, variables: dict[str, Any]) -> None:
        self.variables = variables

    def visit(self, node: ast.AST) -> Any:
        """Dispatch to specific visitor or reject."""
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, None)
        if visitor is None:
            raise UnsafeExpressionError(
                f"Unsafe expression: {node.__class__.__name__} not allowed"
            )
        return visitor(node)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        """Allow int, float, str, bool, None literals."""
        if isinstance(node.value, (int, float, str, bool, type(None))):
            return node.value
        raise UnsafeExpressionError(
            f"Unsafe literal type: {type(node.value).__name__}"
        )

    def visit_Name(self, node: ast.Name) -> Any:
        """Look up variable in context."""
        if node.id in self.variables:
            return self.variables[node.id]
        raise UnsafeExpressionError(f"Unknown variable: {node.id}")

    def visit_Compare(self, node: ast.Compare) -> Any:
        """Evaluate comparison chains: X > Y, X == Y, etc."""
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if isinstance(op, ast.Gt):
                result = left > right
            elif isinstance(op, ast.GtE):
                result = left >= right
            elif isinstance(op, ast.Lt):
                result = left < right
            elif isinstance(op, ast.LtE):
                result = left <= right
            elif isinstance(op, ast.Eq):
                result = left == right
            elif isinstance(op, ast.NotEq):
                result = left != right
            elif isinstance(op, ast.Is):
                result = left is right
            elif isinstance(op, ast.IsNot):
                result = left is not right
            else:
                raise UnsafeExpressionError(
                    f"Unsafe comparison operator: {op.__class__.__name__}"
                )
            if not result:
                return False
            left = right
        return True

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        """Support 'and' / 'or' boolean operators."""
        if isinstance(node.op, ast.And):
            for value in node.values:
                result = self.visit(value)
                if not result:
                    return False
            return result
        elif isinstance(node.op, ast.Or):
            for value in node.values:
                result = self.visit(value)
                if result:
                    return result
            return result
        raise UnsafeExpressionError(
            f"Unsafe boolean operator: {node.op.__class__.__name__}"
        )

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        """Support 'not' unary operator."""
        if isinstance(node.op, ast.Not):
            return not self.visit(node.operand)
        raise UnsafeExpressionError(
            f"Unsafe unary operator: {node.op.__class__.__name__}"
        )

    def visit_Call(self, node: ast.Call) -> Any:
        """Only allow len() function calls."""
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpressionError("Unsafe function call: only len() is allowed")
        if node.func.id != "len":
            raise UnsafeExpressionError(
                f"Unsafe function call: {node.func.id}() not allowed (only len())"
            )
        if len(node.args) != 1:
            raise UnsafeExpressionError("len() requires exactly 1 argument")
        if node.keywords:
            raise UnsafeExpressionError("len() does not accept keyword arguments")
        arg = self.visit(node.args[0])
        return len(arg)


def safe_eval_condition(expression: str, variables: dict[str, Any]) -> bool:
    """Evaluate a condition expression safely using AST parsing.

    Supports ONLY:
    - Comparisons: X > N, X < N, X >= N, X <= N, X == Y, X != Y
    - Function calls: len(X)
    - Variables: resolved from step output context
    - Literals: integers, strings, booleans, None
    - Boolean operators: and, or, not

    NO eval(), NO exec(), NO arbitrary code execution.

    Args:
        expression: The condition expression string.
        variables: Dict mapping variable names to their values.
            Step outputs are keyed by step_id.

    Returns:
        Boolean result of the condition evaluation.

    Raises:
        UnsafeExpressionError: If the expression contains unsafe constructs.
    """
    # Resolve template variables like {{step_id.output}}
    resolved_expr, resolved_vars = _resolve_template_vars(expression, variables)

    try:
        tree = ast.parse(resolved_expr, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Invalid expression syntax: {exc}") from exc

    evaluator = _SafeEvaluator(resolved_vars)
    result = evaluator.visit(tree)
    return bool(result)
