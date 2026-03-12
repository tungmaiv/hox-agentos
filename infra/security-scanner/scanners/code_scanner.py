"""
bandit wrapper: Python SAST (Static Application Security Testing) on source code.

Runs bandit as a subprocess on a temporary .py file.
Returns parsed list of issue dicts from bandit JSON output.
"""
import asyncio
import json
import os
import tempfile


async def scan_code(source_code: str) -> list[dict]:
    """Scan Python source code for security issues using bandit.

    Args:
        source_code: Python source code as string.

    Returns:
        List of issue dicts from bandit JSON output.
        Each dict includes: issue_text, issue_severity, issue_confidence,
        line_number, issue_cwe (optional).
        Returns empty list on empty input or any subprocess error.
    """
    if not source_code.strip():
        return []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(source_code)
        tmp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "bandit",
            "-f", "json",
            "-q",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            data = json.loads(stdout)
            return data.get("results", [])
    except Exception:
        return []
    finally:
        os.unlink(tmp_path)

    return []
