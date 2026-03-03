# backend/tests/test_prompts.py
"""
Unit tests for core/prompts.py — PromptLoader module.

Covers: cache hit, dev-mode bypass, clear_cache, FileNotFoundError,
unmatched placeholder pass-through, and variable substitution.
"""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import core.prompts as prompts_module
from core.prompts import clear_cache, load_prompt


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure each test starts with a clean cache and production mode."""
    clear_cache()
    yield
    clear_cache()


# ── Variable substitution ────────────────────────────────────────────────────


def test_load_prompt_substitutes_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """{{ var }} placeholder is replaced by the supplied keyword argument."""
    (tmp_path / "greeting.md").write_text("Hello {{ name }}!", encoding="utf-8")
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")

    result = load_prompt("greeting", name="World")

    assert result == "Hello World!"
    assert "{{ name }}" not in result


def test_load_prompt_unmatched_placeholder_passes_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A {{ var }} with no matching kwarg is left as-is (no KeyError)."""
    (tmp_path / "template.md").write_text("Hello {{ name }}!", encoding="utf-8")
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")

    result = load_prompt("template")  # no name= kwarg

    assert result == "Hello {{ name }}!"


# ── Caching ──────────────────────────────────────────────────────────────────


def test_production_mode_caches_after_first_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In production mode the file is read once; subsequent calls use cache."""
    prompt_file = tmp_path / "cached.md"
    prompt_file.write_text("original", encoding="utf-8")
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")

    first = load_prompt("cached")

    # Mutate the file on disk — cache should prevent re-read
    prompt_file.write_text("mutated", encoding="utf-8")
    second = load_prompt("cached")

    assert first == "original"
    assert second == "original"  # served from cache


def test_production_mode_does_not_reread_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify cache hit by patching read_text and asserting it's called once."""
    prompt_file = tmp_path / "once.md"
    prompt_file.write_text("content", encoding="utf-8")
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")

    with patch.object(Path, "read_text", wraps=prompt_file.read_text) as mock_read:
        load_prompt("once")
        load_prompt("once")
        load_prompt("once")

    assert mock_read.call_count == 1


# ── Dev-mode cache bypass ────────────────────────────────────────────────────


def test_dev_mode_bypasses_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In dev mode each call reads from disk — file mutations are visible immediately."""
    prompt_file = tmp_path / "hot.md"
    prompt_file.write_text("v1", encoding="utf-8")
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "development")

    first = load_prompt("hot")
    prompt_file.write_text("v2", encoding="utf-8")
    second = load_prompt("hot")

    assert first == "v1"
    assert second == "v2"  # picked up without restart


def test_dev_mode_does_not_populate_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dev-mode reads must not fill _cache (so switching back to prod starts clean)."""
    (tmp_path / "nocache.md").write_text("data", encoding="utf-8")
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "development")

    load_prompt("nocache")

    assert "nocache" not in prompts_module._cache


# ── clear_cache ──────────────────────────────────────────────────────────────


def test_clear_cache_empties_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "x.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")

    load_prompt("x")
    assert "x" in prompts_module._cache

    clear_cache()
    assert prompts_module._cache == {}


# ── FileNotFoundError ────────────────────────────────────────────────────────


def test_missing_prompt_raises_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_prompt raises FileNotFoundError with the missing file path in the message."""
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(FileNotFoundError, match="does_not_exist"):
        load_prompt("does_not_exist")


def test_missing_prompt_error_message_includes_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The error message names the expected .md path so developers know what to create."""
    monkeypatch.setattr(prompts_module, "_prompts_dir", lambda: tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(FileNotFoundError) as exc_info:
        load_prompt("missing_prompt")

    assert "missing_prompt.md" in str(exc_info.value)
