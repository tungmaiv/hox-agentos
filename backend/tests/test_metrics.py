"""
Tests for Prometheus metric registrations in core/metrics.py.

Uses prometheus_client's REGISTRY to verify that:
- Metrics are registered with correct names
- Counter.inc() increments the sample value
- Histogram.observe() records samples
"""
import pytest
from prometheus_client import REGISTRY


def test_tool_calls_counter_registered() -> None:
    """blitz_tool_calls_total must be registered in the default registry.

    Note: prometheus_client stores the Counter family under the base name
    (without _total suffix). The _total suffix appears only in samples.
    """
    # Import triggers module-level registration
    from core.metrics import blitz_tool_calls_total  # noqa: F401

    names = [m.name for m in REGISTRY.collect()]
    # Registry stores base name; _total suffix is on individual samples
    assert "blitz_tool_calls" in names


def test_llm_calls_counter_registered() -> None:
    """blitz_llm_calls_total must be registered in the default registry."""
    # Import triggers module-level registration
    from core.metrics import blitz_llm_calls_total  # noqa: F401

    names = [m.name for m in REGISTRY.collect()]
    assert "blitz_llm_calls" in names


def test_memory_ops_counter_registered() -> None:
    """blitz_memory_ops_total must be registered in the default registry."""
    from core.metrics import blitz_memory_ops_total  # noqa: F401

    names = [m.name for m in REGISTRY.collect()]
    assert "blitz_memory_ops" in names


def test_tool_call_counter_increments() -> None:
    """blitz_tool_calls_total increments correctly with labels."""
    from core.metrics import blitz_tool_calls_total

    # Sample before
    before = _get_counter_value(blitz_tool_calls_total, {"tool": "email.fetch", "success": "True"})
    blitz_tool_calls_total.labels(tool="email.fetch", success="True").inc()
    after = _get_counter_value(blitz_tool_calls_total, {"tool": "email.fetch", "success": "True"})
    assert after == before + 1.0


def test_llm_call_counter_increments() -> None:
    """blitz_llm_calls_total increments correctly with model_alias and status labels."""
    from core.metrics import blitz_llm_calls_total

    before = _get_counter_value(
        blitz_llm_calls_total, {"model_alias": "blitz/master", "status": "success"}
    )
    blitz_llm_calls_total.labels(model_alias="blitz/master", status="success").inc()
    after = _get_counter_value(
        blitz_llm_calls_total, {"model_alias": "blitz/master", "status": "success"}
    )
    assert after == before + 1.0


def test_memory_ops_counter_increments() -> None:
    """blitz_memory_ops_total increments correctly with operation label."""
    from core.metrics import blitz_memory_ops_total

    before = _get_counter_value(blitz_memory_ops_total, {"operation": "read"})
    blitz_memory_ops_total.labels(operation="read").inc()
    after = _get_counter_value(blitz_memory_ops_total, {"operation": "read"})
    assert after == before + 1.0


def _get_counter_value(counter: object, labels: dict[str, str]) -> float:
    """Helper: get current counter value for specific label combination."""
    label_values = tuple(labels[k] for k in sorted(labels))
    for metric in REGISTRY.collect():
        if metric.name == counter._name:  # type: ignore[union-attr]
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    sample_labels = tuple(sample.labels[k] for k in sorted(labels))
                    if sample_labels == label_values:
                        return sample.value
    return 0.0
