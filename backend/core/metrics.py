"""
Prometheus metric registrations for Blitz AgentOS.

All metrics are registered at module level so they are shared across
the process. Import this module to get the singleton metric objects.

Label cardinality rule: All labels are low-cardinality (tool names,
model aliases, operation types). NEVER add user_id as a metric label —
per-user data is available in LiteLLM's Prometheus metrics.
"""
from prometheus_client import Counter, Histogram

# Tool call metrics — instrumented in security/acl.py log_tool_call()
blitz_tool_calls_total = Counter(
    "blitz_tool_calls_total",
    "Total tool calls by tool name and allowed status",
    ["tool", "success"],
)
blitz_tool_duration_seconds = Histogram(
    "blitz_tool_duration_seconds",
    "Tool execution latency in seconds",
    ["tool"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# LLM call metrics — instrumented in core/config.py get_llm() wrapper
blitz_llm_calls_total = Counter(
    "blitz_llm_calls_total",
    "Total LLM calls by model alias and status",
    ["model_alias", "status"],
)
blitz_llm_duration_seconds = Histogram(
    "blitz_llm_duration_seconds",
    "LLM call duration in seconds",
    ["model_alias"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

# Memory operation metrics — instrumented in memory/short_term.py and memory/long_term.py
blitz_memory_ops_total = Counter(
    "blitz_memory_ops_total",
    "Total memory operations by type",
    ["operation"],  # read, write, search
)
blitz_memory_duration_seconds = Histogram(
    "blitz_memory_duration_seconds",
    "Memory operation duration in seconds",
    ["operation"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)
