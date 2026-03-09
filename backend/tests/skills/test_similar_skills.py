"""
Wave 0 test stubs for similar skill search and fork.

SKBLD-04: Search returns top-k similar skills from skill_repo_index using cosine distance
SKBLD-05: Fork external skill copies metadata + source_url attribution into builder state

These stubs exist so Plans 02-04 can import the test module and write implementations
without merge conflicts. Marked xfail — will be filled in by Plan 03.
"""
import pytest


@pytest.mark.xfail(reason="Wave 0 stub — implemented in plan 03")
def test_search_similar_returns_top_k() -> None:
    """SKBLD-04: search_similar_skills() returns top-k results ordered by cosine distance."""
    assert False


@pytest.mark.xfail(reason="Wave 0 stub — implemented in plan 03")
def test_fork_external_skill() -> None:
    """SKBLD-05: fork_skill() populates fork_source and prefills builder state fields."""
    assert False
