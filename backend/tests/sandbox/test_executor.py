"""
Unit tests for SandboxExecutor — Docker SDK calls are fully mocked.
No Docker daemon required to run these tests.
"""
from unittest.mock import MagicMock

import docker.errors
import pytest

from sandbox.executor import SandboxExecutor, SandboxResult


# ── Fixture: mock docker.from_env() ────────────────────────────────────────

@pytest.fixture
def mock_docker(mocker):
    """Patch docker.from_env at the module level so SandboxExecutor uses the mock."""
    mock_client = MagicMock()
    mocker.patch("sandbox.executor.docker.from_env", return_value=mock_client)
    return mock_client


# ── Helper: build a mock container response for containers.run() ──────────

def _make_mock_container(stdout: bytes = b"hello\n", exit_code: int = 0) -> MagicMock:
    """Return a MagicMock that looks like a docker container run result."""
    mock_container = MagicMock()
    mock_container.decode.return_value = stdout.decode("utf-8")
    # containers.run() with stdout=True returns the raw bytes output
    return stdout, mock_container


# ── Test 1: execute returns a valid SandboxResult on success ───────────────

def test_execute_returns_sandbox_result(mock_docker):
    """
    containers.run() returns bytes output.
    SandboxResult should have stdout="hello\n", exit_code=0, timed_out=False.
    """
    mock_docker.containers.run.return_value = b"hello\n"

    executor = SandboxExecutor()
    result = executor.execute(code="print('hello')", language="python")

    assert isinstance(result, SandboxResult)
    assert result.stdout == "hello\n"
    assert result.exit_code == 0
    assert result.timed_out is False


# ── Test 2: execute applies resource limits ─────────────────────────────────

def test_execute_applies_resource_limits(mock_docker):
    """
    containers.run() must be called with:
      nano_cpus=500_000_000, mem_limit="256m", network_disabled=True
    """
    mock_docker.containers.run.return_value = b""

    executor = SandboxExecutor()
    executor.execute(code="pass", language="python")

    call_kwargs = mock_docker.containers.run.call_args[1]
    assert call_kwargs.get("nano_cpus") == 500_000_000, (
        f"Expected nano_cpus=500_000_000, got {call_kwargs.get('nano_cpus')}"
    )
    assert call_kwargs.get("mem_limit") == "256m", (
        f"Expected mem_limit='256m', got {call_kwargs.get('mem_limit')}"
    )
    assert call_kwargs.get("network_disabled") is True, (
        f"Expected network_disabled=True, got {call_kwargs.get('network_disabled')}"
    )


# ── Test 3: execute applies read-only filesystem ────────────────────────────

def test_execute_applies_readonly_filesystem(mock_docker):
    """
    containers.run() must be called with read_only=True and tmpfs parameter.
    """
    mock_docker.containers.run.return_value = b""

    executor = SandboxExecutor()
    executor.execute(code="pass", language="python")

    call_kwargs = mock_docker.containers.run.call_args[1]
    assert call_kwargs.get("read_only") is True, (
        f"Expected read_only=True, got {call_kwargs.get('read_only')}"
    )
    assert "tmpfs" in call_kwargs, "Expected tmpfs parameter in containers.run() call"
    assert "/tmp" in call_kwargs["tmpfs"], "Expected /tmp in tmpfs dict"


# ── Test 4: execute labels containers with blitz.sandbox=true ───────────────

def test_execute_labels_containers(mock_docker):
    """
    All sandbox containers must carry labels={"blitz.sandbox": "true"}
    for leaked container cleanup identification.
    """
    mock_docker.containers.run.return_value = b""

    executor = SandboxExecutor()
    executor.execute(code="pass", language="python")

    call_kwargs = mock_docker.containers.run.call_args[1]
    labels = call_kwargs.get("labels", {})
    assert labels.get("blitz.sandbox") == "true", (
        f"Expected labels={{'blitz.sandbox': 'true'}}, got {labels}"
    )


# ── Test 5: timeout causes container removal and timed_out=True ─────────────

def test_execute_timeout_removes_container(mock_docker):
    """
    When containers.run() raises ContainerError, the executor must:
    1. Call container.remove(force=True) OR use auto_remove=True
    2. Return SandboxResult with timed_out=True (when error message contains 'timeout')
    """
    # ContainerError requires container, exit_status, and output arguments
    mock_container = MagicMock()
    mock_docker.containers.run.side_effect = docker.errors.ContainerError(
        container=mock_container,
        exit_status=137,
        command="python -c pass",
        image="python:3.12-alpine",
        stderr=b"timeout: killed",
    )

    executor = SandboxExecutor()
    result = executor.execute(code="while True: pass", language="python", timeout=1)

    assert isinstance(result, SandboxResult)
    assert result.timed_out is True
    # Container must be force-removed on error (unless auto_remove=True is set)
    # Accept either: auto_remove=True in kwargs, OR remove(force=True) called
    call_kwargs = mock_docker.containers.run.call_args[1]
    if not call_kwargs.get("remove", False):
        mock_container.remove.assert_called_once_with(force=True)


# ── Test 6: cleanup removes all labeled containers ───────────────────────────

def test_cleanup_leaked_containers_removes_labeled_containers(mock_docker):
    """
    _cleanup_leaked_containers() must:
    1. Call containers.list(all=True, filters={"label": "blitz.sandbox=true"})
    2. Call remove(force=True) on each returned container
    """
    mock_leaked = MagicMock()
    mock_docker.containers.list.return_value = [mock_leaked]

    executor = SandboxExecutor()
    executor._cleanup_leaked_containers()

    mock_docker.containers.list.assert_called_once_with(
        all=True, filters={"label": "blitz.sandbox=true"}
    )
    mock_leaked.remove.assert_called_once_with(force=True)
