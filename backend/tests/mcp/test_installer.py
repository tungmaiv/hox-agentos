"""TDD tests for MCPInstaller — mock asyncio.create_subprocess_exec."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


def _make_proc(returncode: int) -> MagicMock:
    """Create a mock subprocess with given returncode."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", b"error output"))
    return proc


# ---------------------------------------------------------------------------
# Tests: install()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_npm_install_calls_correct_command() -> None:
    """install('npm', '@upstash/context7-mcp') calls subprocess with correct npm command."""
    from mcp.installer import MCPInstaller  # type: ignore[import]

    installer = MCPInstaller()
    mock_proc = _make_proc(returncode=0)

    with patch("mcp.installer.asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)) as mock_exec:
        await installer.install("npm", "@upstash/context7-mcp")

    mock_exec.assert_called_once_with(
        "npm", "install", "-g", "@upstash/context7-mcp",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


@pytest.mark.asyncio
async def test_pip_install_calls_correct_command() -> None:
    """install('pip', 'mcp-server-fetch') calls subprocess with correct pip command."""
    from mcp.installer import MCPInstaller  # type: ignore[import]

    installer = MCPInstaller()
    mock_proc = _make_proc(returncode=0)

    with patch("mcp.installer.asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)) as mock_exec:
        await installer.install("pip", "mcp-server-fetch")

    mock_exec.assert_called_once_with(
        "pip", "install", "mcp-server-fetch",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


@pytest.mark.asyncio
async def test_install_raises_on_nonzero_exit() -> None:
    """Subprocess returns exit code 1; install() raises MCPInstallError."""
    from mcp.installer import MCPInstaller, MCPInstallError  # type: ignore[import]

    installer = MCPInstaller()
    mock_proc = _make_proc(returncode=1)

    with patch("mcp.installer.asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
        with pytest.raises(MCPInstallError):
            await installer.install("npm", "@upstash/context7-mcp")


@pytest.mark.asyncio
async def test_unknown_package_manager_raises() -> None:
    """install('yarn', 'pkg') raises ValueError."""
    from mcp.installer import MCPInstaller  # type: ignore[import]

    installer = MCPInstaller()
    with pytest.raises(ValueError, match="Unknown package manager"):
        await installer.install("yarn", "some-pkg")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: is_installed()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_installed_returns_true_on_zero_exit() -> None:
    """Mock subprocess returns exit code 0; is_installed returns True."""
    from mcp.installer import MCPInstaller  # type: ignore[import]

    installer = MCPInstaller()
    mock_proc = _make_proc(returncode=0)

    with patch("mcp.installer.asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
        result = await installer.is_installed("npm", "@upstash/context7-mcp")

    assert result is True


@pytest.mark.asyncio
async def test_is_installed_returns_false_on_nonzero_exit() -> None:
    """Mock subprocess returns exit code 1; is_installed returns False."""
    from mcp.installer import MCPInstaller  # type: ignore[import]

    installer = MCPInstaller()
    mock_proc = _make_proc(returncode=1)

    with patch("mcp.installer.asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
        result = await installer.is_installed("pip", "mcp-server-fetch")

    assert result is False
