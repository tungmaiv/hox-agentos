import pytest
from agents.condition_evaluator import evaluate_condition


# ── Comparison operators ──────────────────────────────────────────────────────

def test_greater_than_true():
    assert evaluate_condition("output.count > 0", {"count": 5}) is True

def test_greater_than_false():
    assert evaluate_condition("output.count > 0", {"count": 0}) is False

def test_less_than_true():
    assert evaluate_condition("output.count < 10", {"count": 3}) is True

def test_equal_bool_true():
    assert evaluate_condition("output.matched == true", {"matched": True}) is True

def test_equal_bool_false():
    assert evaluate_condition("output.matched == true", {"matched": False}) is False

def test_not_equal_string():
    assert evaluate_condition("output.status != 'error'", {"status": "ok"}) is True

def test_equal_string():
    assert evaluate_condition("output.status == 'active'", {"status": "active"}) is True


# ── String operations ─────────────────────────────────────────────────────────

def test_contains_true():
    assert evaluate_condition("output.contains('URGENT')", "URGENT: fix this") is True

def test_contains_false():
    assert evaluate_condition("output.contains('URGENT')", "normal message") is False

def test_contains_in_dict_stringified():
    # When output is a dict, it's stringified for contains check
    assert evaluate_condition("output.contains('hello')", {"message": "hello world"}) is True


# ── is_empty ─────────────────────────────────────────────────────────────────

def test_is_empty_list_true():
    assert evaluate_condition("output.is_empty", []) is True

def test_is_empty_list_false():
    assert evaluate_condition("output.is_empty", [1, 2]) is False

def test_is_empty_string_true():
    assert evaluate_condition("output.is_empty", "") is True

def test_is_empty_none_true():
    assert evaluate_condition("output.is_empty", None) is True


# ── Security: unsupported expressions rejected ────────────────────────────────

def test_rejects_arbitrary_code():
    with pytest.raises(ValueError, match="Unsupported expression"):
        evaluate_condition("import os; os.system('rm -rf /')", {})

def test_rejects_eval():
    with pytest.raises(ValueError, match="Unsupported expression"):
        evaluate_condition("eval('1+1')", {})

def test_rejects_unknown_form():
    with pytest.raises(ValueError, match="Unsupported expression"):
        evaluate_condition("output.foo.bar.baz", {})
