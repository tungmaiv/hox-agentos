"""
detect-secrets wrapper: scans source code for hardcoded secrets (API keys, passwords, tokens).

Runs detect-secrets as a subprocess on a temporary file.
Returns True if any secrets are detected.
"""
import asyncio
import json
import os
import tempfile


async def scan_secrets(source_code: str) -> bool:
    """Scan Python source code for hardcoded secrets using detect-secrets.

    Args:
        source_code: Source code as string.

    Returns:
        True if any secrets are detected, False otherwise.
        Returns False on empty input or any subprocess error.
    """
    if not source_code.strip():
        return False

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(source_code)
        tmp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "detect-secrets",
            "scan",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            data = json.loads(stdout)
            # results dict maps filename -> list of potential secrets
            return bool(data.get("results", {}))
    except Exception:
        return False
    finally:
        os.unlink(tmp_path)

    return False
