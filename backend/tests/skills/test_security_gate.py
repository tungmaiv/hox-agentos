"""
Wave 0 test stubs for builder security gate.

SKBLD-06: Builder save path: approved skills saved directly; below-threshold skills
          create pending_review rows requiring admin action.
SKBLD-08: Builder inline approval: admin can approve/reject pending skills inline
          in the builder UI without leaving the page.

These stubs exist so Plans 02-04 can import the test module and write implementations
without merge conflicts. Marked xfail — will be filled in by Plan 04.
"""
import pytest


@pytest.mark.xfail(reason="Wave 0 stub — implemented in plan 04")
def test_builder_save_approve() -> None:
    """SKBLD-06: Save skill with score >= threshold → saved directly as active."""
    assert False


@pytest.mark.xfail(reason="Wave 0 stub — implemented in plan 04")
def test_builder_save_pending_review() -> None:
    """SKBLD-06: Save skill with score < threshold → pending_review row created."""
    assert False


@pytest.mark.xfail(reason="Wave 0 stub — implemented in plan 04")
def test_builder_inline_approve() -> None:
    """SKBLD-08: Admin approves pending skill inline in builder → skill activated."""
    assert False
