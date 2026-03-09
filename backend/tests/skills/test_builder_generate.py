"""
Wave 0 test stubs for skill builder content generation.

SKBLD-01: Builder generates substantive procedural skill content (not blank template)
SKBLD-02: Builder generates substantive instructional skill content (not blank template)
SKBLD-03: Builder generates Python handler stub for tool artifacts

These stubs exist so Plans 02-04 can import the test module and write implementations
without merge conflicts. Marked xfail — will be filled in by Plan 02.
"""
import pytest


@pytest.mark.xfail(reason="Wave 0 stub — implemented in plan 02")
def test_generate_procedural_skill_content() -> None:
    """SKBLD-01: Builder LLM call generates non-empty procedural skill body."""
    assert False


@pytest.mark.xfail(reason="Wave 0 stub — implemented in plan 02")
def test_generate_instructional_skill_content() -> None:
    """SKBLD-02: Builder LLM call generates non-empty instructional skill body."""
    assert False


@pytest.mark.xfail(reason="Wave 0 stub — implemented in plan 02")
def test_generate_tool_stub() -> None:
    """SKBLD-03: Builder generates Python handler stub stored in handler_code."""
    assert False
