"""
Sandbox resource limits and policy constants.

All values are intentionally conservative for untrusted code execution.
These constants are used by SandboxExecutor to configure Docker containers.
"""

SANDBOX_LIMITS: dict = {
    "nano_cpus": 500_000_000,                   # 0.5 CPU cores
    "mem_limit": "256m",                         # 256MB hard limit
    "network_disabled": True,                    # no outbound network
    "read_only": True,                           # read-only root filesystem
    "tmpfs": {"/tmp": "size=64m,mode=777"},      # writable temp space only  # nosec B108 — intentional Docker tmpfs mount, not a host tempfile
    "labels": {"blitz.sandbox": "true"},         # for leaked container cleanup
}

DEFAULT_TIMEOUT: int = 30    # seconds
MAX_TIMEOUT: int = 120       # seconds — enforced ceiling for caller-provided values
