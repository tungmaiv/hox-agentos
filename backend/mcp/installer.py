"""MCPInstaller: install npm/pip packages for stdio MCP servers."""
import asyncio
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)


class MCPInstallError(Exception):
    """Raised when an npm or pip install command exits with a non-zero code."""


class MCPInstaller:
    """Installs and checks MCP server packages via npm or pip."""

    async def install(
        self,
        package_manager: Literal["npm", "pip"],
        package_name: str,
    ) -> None:
        """Install an MCP server package.

        Args:
            package_manager: "npm" or "pip"
            package_name: The package identifier (e.g., "@upstash/context7-mcp")

        Raises:
            ValueError: if package_manager is not "npm" or "pip"
            MCPInstallError: if the subprocess exits with a non-zero return code
        """
        if package_manager == "npm":
            cmd = ["npm", "install", "-g", package_name]
        elif package_manager == "pip":
            cmd = ["pip", "install", package_name]
        else:
            raise ValueError(
                f"Unknown package manager: {package_manager!r}. Use 'npm' or 'pip'."
            )

        logger.info(
            "mcp_install",
            package_manager=package_manager,
            package=package_name,
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise MCPInstallError(
                f"{package_manager} install {package_name!r} failed"
                f" (exit {proc.returncode}): {stderr.decode()}"
            )

        logger.info(
            "mcp_install_success",
            package_manager=package_manager,
            package=package_name,
        )

    async def is_installed(
        self,
        package_manager: Literal["npm", "pip"],
        package_name: str,
    ) -> bool:
        """Check whether an MCP package is already installed.

        Args:
            package_manager: "npm" or "pip"
            package_name: The package identifier

        Returns:
            True if the check command exits 0, False otherwise.
        """
        if package_manager == "npm":
            cmd = ["npm", "list", "-g", package_name]
        elif package_manager == "pip":
            cmd = ["pip", "show", package_name]
        else:
            return False

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0
