"""
Tests for workflow template JSON fixtures.

Validates that the pre-built workflow templates (morning_digest.json, alert.json)
conform to the expected schema: correct schema_version, required node types,
and valid edges (all edge source/target reference existing node IDs).

These are pure JSON validation tests — no DB or HTTP required.
"""
import json
import pathlib
from typing import Any

import pytest

# Path to the fixture files
FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "data" / "workflow_templates"


def load_fixture(filename: str) -> dict[str, Any]:
    """Load and parse a JSON fixture file."""
    path = FIXTURES_DIR / filename
    assert path.exists(), f"Fixture file not found: {path}"
    return json.loads(path.read_text())


def get_node_ids(data: dict[str, Any]) -> set[str]:
    """Extract all node IDs from a workflow fixture."""
    return {node["id"] for node in data.get("nodes", [])}


def get_node_types(data: dict[str, Any]) -> set[str]:
    """Extract all unique node types from a workflow fixture."""
    return {node["type"] for node in data.get("nodes", [])}


# ── Morning Digest tests ──────────────────────────────────────────────────────


def test_morning_digest_schema_version() -> None:
    """morning_digest.json must have schema_version == '1.0'."""
    data = load_fixture("morning_digest.json")
    assert data["schema_version"] == "1.0"


def test_morning_digest_has_required_node_types() -> None:
    """morning_digest.json must contain: trigger_node, tool_node, condition_node, agent_node, channel_output_node."""
    data = load_fixture("morning_digest.json")
    node_types = get_node_types(data)
    required = {"trigger_node", "tool_node", "condition_node", "agent_node", "channel_output_node"}
    missing = required - node_types
    assert not missing, f"morning_digest.json missing node types: {missing}"


def test_morning_digest_edges_connect_to_existing_nodes() -> None:
    """All edges in morning_digest.json must reference valid node IDs."""
    data = load_fixture("morning_digest.json")
    node_ids = get_node_ids(data)
    for edge in data.get("edges", []):
        assert edge["source"] in node_ids, (
            f"Edge {edge['id']}: source '{edge['source']}' not in node IDs {node_ids}"
        )
        assert edge["target"] in node_ids, (
            f"Edge {edge['id']}: target '{edge['target']}' not in node IDs {node_ids}"
        )


# ── Alert tests ───────────────────────────────────────────────────────────────


def test_alert_schema_version() -> None:
    """alert.json must have schema_version == '1.0'."""
    data = load_fixture("alert.json")
    assert data["schema_version"] == "1.0"


def test_alert_has_required_node_types() -> None:
    """alert.json must contain: trigger_node, tool_node, condition_node, channel_output_node."""
    data = load_fixture("alert.json")
    node_types = get_node_types(data)
    required = {"trigger_node", "tool_node", "condition_node", "channel_output_node"}
    missing = required - node_types
    assert not missing, f"alert.json missing node types: {missing}"


def test_alert_edges_connect_to_existing_nodes() -> None:
    """All edges in alert.json must reference valid node IDs."""
    data = load_fixture("alert.json")
    node_ids = get_node_ids(data)
    for edge in data.get("edges", []):
        assert edge["source"] in node_ids, (
            f"Edge {edge['id']}: source '{edge['source']}' not in node IDs {node_ids}"
        )
        assert edge["target"] in node_ids, (
            f"Edge {edge['id']}: target '{edge['target']}' not in node IDs {node_ids}"
        )
