"""
Regression tests for LLM call metric instrumentation in core/config.py.

Verifies that blitz_llm_calls_total is incremented by _LLMMetricsCallback
when an LLM call completes (on_llm_end) or fails (on_llm_error).

Strategy: call the callback methods directly on the callback instance
(simulating what LangChain would do internally). This avoids needing
a live LiteLLM connection while still testing the metric wiring end-to-end.

Uses delta assertions (before/after) to be robust against shared prometheus
REGISTRY state across test sessions.
"""
from prometheus_client import REGISTRY


def _get_counter_value(counter: object, labels: dict[str, str]) -> float:
    """Get current counter value for a specific label combination."""
    label_values = tuple(labels[k] for k in sorted(labels))
    for metric in REGISTRY.collect():
        if metric.name == counter._name:  # type: ignore[union-attr]
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    sample_labels = tuple(sample.labels[k] for k in sorted(labels))
                    if sample_labels == label_values:
                        return sample.value
    return 0.0


def test_llm_metrics_callback_increments_on_success() -> None:
    """_LLMMetricsCallback.on_llm_end increments blitz_llm_calls_total{status='success'}.

    Regression: before the fix, blitz_llm_calls_total was never incremented —
    the metric was defined but the callback was missing from get_llm().
    """
    from core.config import _LLMMetricsCallback
    from core.metrics import blitz_llm_calls_total

    alias = "blitz/master"
    before = _get_counter_value(
        blitz_llm_calls_total, {"model_alias": alias, "status": "success"}
    )

    # Simulate LangChain firing on_llm_end after a successful call
    cb = _LLMMetricsCallback(alias)
    cb.on_llm_end(response=object())  # response arg is ignored by our callback

    after = _get_counter_value(
        blitz_llm_calls_total, {"model_alias": alias, "status": "success"}
    )
    assert after == before + 1.0, (
        f"Expected blitz_llm_calls_total{{model_alias='{alias}', status='success'}} "
        f"to increment by 1.0, got delta {after - before}"
    )


def test_llm_metrics_callback_increments_on_error() -> None:
    """_LLMMetricsCallback.on_llm_error increments blitz_llm_calls_total{status='error'}."""
    from core.config import _LLMMetricsCallback
    from core.metrics import blitz_llm_calls_total

    alias = "blitz/fast"
    before = _get_counter_value(
        blitz_llm_calls_total, {"model_alias": alias, "status": "error"}
    )

    cb = _LLMMetricsCallback(alias)
    cb.on_llm_error(error=RuntimeError("LiteLLM timeout"))

    after = _get_counter_value(
        blitz_llm_calls_total, {"model_alias": alias, "status": "error"}
    )
    assert after == before + 1.0


def test_get_llm_returns_client_with_callback() -> None:
    """get_llm() returns a ChatOpenAI instance with _LLMMetricsCallback in callbacks.

    Regression: before the fix, get_llm() returned a bare ChatOpenAI with no callbacks.
    """
    from core.config import _LLMMetricsCallback, get_llm

    llm = get_llm("blitz/master")
    # LangChain stores callbacks in llm.callbacks list
    callbacks = llm.callbacks or []
    callback_types = [type(cb) for cb in callbacks]
    assert _LLMMetricsCallback in callback_types, (
        f"Expected _LLMMetricsCallback in get_llm().callbacks, "
        f"but found: {callback_types}. "
        f"The metric callback is not wired into get_llm()."
    )
