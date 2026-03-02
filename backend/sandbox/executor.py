"""
Docker sandbox executor for untrusted code execution.

Architecture:
- SandboxExecutor wraps the Docker Python SDK to execute untrusted code in
  isolated containers with enforced resource limits.
- Each execution gets a fresh container that is destroyed immediately after.
- Resource limits are sourced from sandbox.policies.SANDBOX_LIMITS.
- All containers are labelled "blitz.sandbox=true" for leak detection.

Security invariants:
- CPU: 0.5 cores max (nano_cpus = 500_000_000)
- Memory: 256MB hard limit
- Network: disabled (network_disabled=True prevents ALL outbound traffic)
- Filesystem: read-only root; /tmp is a size-limited tmpfs (no host mounts)
- Container is auto-removed or force-removed in all code paths

Usage:
    executor = SandboxExecutor()
    result = executor.execute(code="print('hello')", language="python")
    # SandboxResult(stdout="hello\n", exit_code=0, timed_out=False, ...)
"""
import structlog
from pydantic import BaseModel, Field

import docker
import docker.errors

from sandbox.policies import DEFAULT_TIMEOUT, MAX_TIMEOUT, SANDBOX_LIMITS

logger = structlog.get_logger(__name__)

# Container image per language — only Python supported in MVP.
_LANGUAGE_IMAGES: dict[str, str] = {
    "python": "python:3.12-alpine",
}
_DEFAULT_IMAGE = "python:3.12-alpine"


class SandboxResult(BaseModel):
    """Structured result from a sandboxed code execution."""

    stdout: str = Field(default="", description="Captured stdout from the container")
    stderr: str = Field(default="", description="Captured stderr from the container")
    exit_code: int = Field(default=0, description="Container exit status code")
    timed_out: bool = Field(default=False, description="True if execution was killed by timeout")
    container_id: str | None = Field(
        default=None,
        description="Docker container ID (None if container was auto-removed or never started)",
    )


class SandboxExecutor:
    """
    Executes untrusted code in isolated Docker containers with enforced limits.

    Each call to execute() spins up a fresh container, runs the code, collects
    the output, and destroys the container. No state is shared between calls.
    """

    def __init__(self) -> None:
        self._client: docker.DockerClient | None = None

    def _get_client(self) -> docker.DockerClient:
        """Lazy-initialize Docker client on first use (not at import time)."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def _get_image(self, language: str) -> str:
        """Return the Docker image for the given programming language."""
        return _LANGUAGE_IMAGES.get(language.lower(), _DEFAULT_IMAGE)

    def _build_command(self, code: str, language: str) -> list[str]:
        """Build the container command to execute code in the given language."""
        if language.lower() == "python":
            return ["python", "-c", code]
        # Fallback: treat as shell command (not currently supported in MVP)
        return ["sh", "-c", code]

    def execute(
        self,
        code: str,
        language: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> SandboxResult:
        """
        Execute untrusted code in an isolated Docker container.

        Args:
            code: Source code to execute.
            language: Programming language (currently only "python" supported).
            timeout: Seconds before the container is killed. Capped at MAX_TIMEOUT.

        Returns:
            SandboxResult with stdout, stderr, exit_code, timed_out, container_id.
        """
        effective_timeout = min(timeout, MAX_TIMEOUT)
        image = self._get_image(language)
        command = self._build_command(code, language)

        logger.info(
            "sandbox_execute_start",
            language=language,
            image=image,
            timeout=effective_timeout,
        )

        try:
            output = self._get_client().containers.run(
                image=image,
                command=command,
                # Resource limits from policies
                nano_cpus=SANDBOX_LIMITS["nano_cpus"],
                mem_limit=SANDBOX_LIMITS["mem_limit"],
                network_disabled=SANDBOX_LIMITS["network_disabled"],
                read_only=SANDBOX_LIMITS["read_only"],
                tmpfs=SANDBOX_LIMITS["tmpfs"],
                labels=SANDBOX_LIMITS["labels"],
                pids_limit=SANDBOX_LIMITS["pids_limit"],
                user=SANDBOX_LIMITS["user"],
                cap_drop=SANDBOX_LIMITS["cap_drop"],
                # Container lifecycle
                remove=True,           # auto-remove after run
                stdout=True,
                stderr=True,           # capture stderr even on zero exit code
                timeout=effective_timeout,
            )

            # When both stdout=True and stderr=True, Docker SDK returns a tuple.
            if isinstance(output, tuple):
                stdout_raw, stderr_raw = output
            else:
                stdout_raw, stderr_raw = output, b""

            stdout = stdout_raw.decode("utf-8") if isinstance(stdout_raw, bytes) else str(stdout_raw)
            stderr_text = stderr_raw.decode("utf-8") if isinstance(stderr_raw, bytes) else str(stderr_raw or "")
            logger.info("sandbox_execute_success", language=language, exit_code=0)
            return SandboxResult(
                stdout=stdout,
                stderr=stderr_text,
                exit_code=0,
                timed_out=False,
                container_id=None,  # auto-removed, no ID available
            )

        except docker.errors.ContainerError as exc:
            # Non-zero exit code from the container (includes OOM kills, explicit exits)
            stderr_text = exc.stderr.decode("utf-8") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
            exit_status = exc.exit_status

            # Detect timeout: Docker sends SIGKILL (exit 137) with "timeout" in stderr
            is_timeout = "timeout" in stderr_text.lower() or exit_status == 137

            logger.warning(
                "sandbox_execute_container_error",
                language=language,
                exit_status=exit_status,
                timed_out=is_timeout,
            )

            # Force-remove the container as a safety net (it may not auto-remove on error)
            container = getattr(exc, "container", None)
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass  # Best-effort cleanup; container may already be gone

            return SandboxResult(
                stdout="",
                stderr=stderr_text,
                exit_code=exit_status,
                timed_out=is_timeout,
                container_id=None,
            )

        except docker.errors.APIError as exc:
            # Docker daemon error (e.g., image not found, resource allocation failure)
            error_msg = str(exc)
            is_timeout = "timeout" in error_msg.lower()

            logger.error(
                "sandbox_execute_api_error",
                language=language,
                error=error_msg,
                timed_out=is_timeout,
            )
            return SandboxResult(
                stdout="",
                stderr=error_msg,
                exit_code=1,
                timed_out=is_timeout,
                container_id=None,
            )

        except Exception as exc:
            logger.error("sandbox_execute_unexpected_error", language=language, error=str(exc))
            return SandboxResult(
                stdout="",
                stderr=str(exc),
                exit_code=1,
                timed_out=False,
                container_id=None,
            )

    def _cleanup_leaked_containers(self) -> None:
        """
        Remove any sandbox containers that were not auto-removed.

        Uses the "blitz.sandbox=true" label to identify leaked containers.
        Called periodically (e.g., on scheduler startup) to prevent resource leaks.
        """
        try:
            leaked = self._get_client().containers.list(
                all=True,
                filters={"label": "blitz.sandbox=true"},
            )
            for container in leaked:
                try:
                    container.remove(force=True)
                    logger.warning(
                        "sandbox_leaked_container_removed",
                        container_id=getattr(container, "id", "unknown"),
                    )
                except Exception as exc:
                    logger.error(
                        "sandbox_cleanup_remove_failed",
                        container_id=getattr(container, "id", "unknown"),
                        error=str(exc),
                    )
        except Exception as exc:
            logger.error("sandbox_cleanup_list_failed", error=str(exc))
