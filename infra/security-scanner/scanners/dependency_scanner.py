"""
pip-audit wrapper: scans requirements.txt content for CVE vulnerabilities.

Runs pip-audit as a subprocess on a temporary requirements.txt file.
Returns parsed list of dependency dicts with vulnerability info.
"""
import asyncio
import json
import os
import tempfile


async def scan_dependencies(requirements_txt: str) -> list[dict]:
    """Scan requirements.txt content for known CVEs using pip-audit.

    Args:
        requirements_txt: Content of requirements.txt (package==version per line).

    Returns:
        List of dependency dicts from pip-audit JSON output.
        Each dict: {"name": str, "version": str, "vulns": [{"id": str, ...}]}
        Returns empty list on empty input or any subprocess error.
    """
    if not requirements_txt.strip():
        return []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(requirements_txt)
        tmp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "pip-audit",
            "--requirement", tmp_path,
            "--format", "json",
            "--no-progress-spinner",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            data = json.loads(stdout)
            return data.get("dependencies", []) if isinstance(data, dict) else []
    except Exception:
        return []
    finally:
        os.unlink(tmp_path)

    return []
