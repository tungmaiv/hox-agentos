"""Tests for AST-based safe expression evaluator."""
import pytest

from skills.safe_eval import UnsafeExpressionError, safe_eval_condition


class TestSafeEvalBasicComparisons:
    """Test basic comparison operators."""

    def test_greater_than_true(self) -> None:
        assert safe_eval_condition("x > 5", {"x": 10}) is True

    def test_greater_than_false(self) -> None:
        assert safe_eval_condition("x > 5", {"x": 3}) is False

    def test_less_than(self) -> None:
        assert safe_eval_condition("x < 10", {"x": 5}) is True

    def test_greater_equal(self) -> None:
        assert safe_eval_condition("x >= 5", {"x": 5}) is True

    def test_less_equal(self) -> None:
        assert safe_eval_condition("x <= 5", {"x": 5}) is True

    def test_equal_string(self) -> None:
        assert safe_eval_condition('x == "active"', {"x": "active"}) is True

    def test_not_equal(self) -> None:
        assert safe_eval_condition('x != "inactive"', {"x": "active"}) is True

    def test_equal_int(self) -> None:
        assert safe_eval_condition("x == 42", {"x": 42}) is True


class TestSafeEvalFunctions:
    """Test allowed function calls."""

    def test_len_nonempty_string(self) -> None:
        assert safe_eval_condition("len(x) > 0", {"x": "hello"}) is True

    def test_len_empty_string(self) -> None:
        assert safe_eval_condition("len(x) > 0", {"x": ""}) is False

    def test_len_list(self) -> None:
        assert safe_eval_condition("len(x) == 3", {"x": [1, 2, 3]}) is True

    def test_len_zero(self) -> None:
        assert safe_eval_condition("len(x) == 0", {"x": []}) is True


class TestSafeEvalBooleanOps:
    """Test boolean operators."""

    def test_and_both_true(self) -> None:
        assert safe_eval_condition(
            'x > 5 and y == "ok"', {"x": 10, "y": "ok"}
        ) is True

    def test_and_one_false(self) -> None:
        assert safe_eval_condition(
            'x > 5 and y == "ok"', {"x": 3, "y": "ok"}
        ) is False

    def test_or_one_true(self) -> None:
        assert safe_eval_condition(
            "x > 5 or y > 5", {"x": 10, "y": 3}
        ) is True

    def test_or_both_false(self) -> None:
        assert safe_eval_condition(
            "x > 5 or y > 5", {"x": 3, "y": 3}
        ) is False

    def test_not_operator(self) -> None:
        assert safe_eval_condition("not x", {"x": False}) is True


class TestSafeEvalTemplateVars:
    """Test {{step_id.output}} template variable resolution."""

    def test_template_var_resolved(self) -> None:
        assert safe_eval_condition(
            "len({{fetch.output}}) > 0", {"fetch": "some data"}
        ) is True

    def test_template_var_comparison(self) -> None:
        assert safe_eval_condition(
            '{{check.output}} == "done"', {"check": "done"}
        ) is True


class TestSafeEvalUnsafeExpressions:
    """Test that unsafe expressions are rejected."""

    def test_import_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_condition("import os", {})

    def test_dunder_import_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_condition("__import__('os')", {})

    def test_attribute_access_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_condition("x.attr", {"x": "test"})

    def test_eval_call_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_condition('eval("1+1")', {})

    def test_exec_call_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_condition('exec("pass")', {})

    def test_subscript_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_condition("x[0]", {"x": [1, 2, 3]})

    def test_lambda_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_condition("(lambda: 1)()", {})

    def test_comprehension_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError):
            safe_eval_condition("[x for x in range(10)]", {})

    def test_unknown_variable_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="Unknown variable"):
            safe_eval_condition("unknown_var > 5", {})

    def test_invalid_syntax_rejected(self) -> None:
        with pytest.raises(UnsafeExpressionError, match="Invalid expression"):
            safe_eval_condition("x >>>", {"x": 1})
