# MCP vs CLI-Anything Evaluation for AgentOS

**Status:** 🟡 DEFERRED to Topic #21 (Universal Integration)
**Decision:** Halt discussion, revisit after universal integration layer is designed
**Date:** 2026-03-14

---

## Executive Summary

**Recommendation:** Hybrid architecture — keep MCP for custom tools, add CLI-Anything wrapper for external software.

### Key Findings

| Aspect | MCP (Current AgentOS) | CLI-Anything |
|---------|------------------------|---------------|
| **Best For** | Custom tools built for AgentOS | Existing software without APIs |
| **Integration Target** | Email, Calendar, CRM (AgentOS-native) | LibreOffice, GIMP, Blender, Shotcut |
| **Development Effort** | High (write server + schemas) | Low (one command generation) |
| **Real-Time Streaming** | ✅ Built-in (HTTP+SSE) | ❌ CLI subprocess output |
| **Tool Discovery** | Dynamic via tool registry | Auto-generated via `/cli-anything` |
| **Security Model** | ✅ Built-in ACL (Gate 3) | ⚠️ File system ACL only |
| **Production Maturity** | New (emerging standard) | ✅ 11 apps, 1,508 tests |

### Proposed Hybrid Architecture

```
AgentOS Tool Registry
├── MCP Tools (custom, real-time)
│   ├── Email Server
│   ├── Calendar Server
│   └── CRM Server
└── CLI-Anything Tools (existing software)
    ├── LibreOffice (cli-anything-libreoffice)
    ├── GIMP (cli-anything-gimp)
    ├── Blender (cli-anything-blender)
    └── Shotcut (cli-anything-shotcut)
```

### Implementation Strategy

**Phase 1 (Current):** Keep MCP for custom tools
- Email, Calendar, CRM MCP servers
- Real-time streaming
- Integrated ACL

**Phase 2 (v1.7+):** Add CLI-Anything wrapper
- Wrapper layer: `backend/tools/cli_wrapper.py`
- Auto-discovery of installed CLI-Anything CLIs
- Register as tools in tool registry

**Phase 3 (Topic #21):** Universal Integration Layer
- Unified adapter framework for both MCP and CLI-Anything
- Consistent security model across all integrations
- Streaming support for CLI-Anything wrappers

### Priority Order for CLI-Anything Integration

1. **High Value:** LibreOffice (documents, spreadsheets)
2. **High Value:** GIMP (image editing)
3. **Medium:** Blender (3D modeling)
4. **Medium:** Shotcut/Kdenlive (video editing)
5. **Low:** Zoom (meetings)

---

## CLI-Anything Wrapper Prototype

```python
# backend/tools/cli_wrapper.py
from typing import Dict, Any
import subprocess
import json

class CLIWrapperTool:
    """Wrapper for CLI-Anything generated CLIs"""

    def __init__(self, cli_name: str, cli_path: str):
        self.cli_name = cli_name
        self.cli_path = cli_path

    async def execute(
        self,
        command: list[str],
        json_output: bool = True,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Execute CLI command and parse output"""

        # Build CLI command
        cmd = [self.cli_path] + command
        if json_output:
            cmd.append("--json")

        # Execute subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Parse JSON output
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            output = {"raw": result.stdout}

        # Handle errors
        if result.returncode != 0:
            raise Exception(
                f"CLI command failed: {result.stderr}",
                returncode=result.returncode,
            )

        return output

# Register CLI-Anything tools in tool_registry.py
register_tool(
    "libreoffice_pdf",
    CLIWrapperTool("libreoffice", "cli-anything-libreoffice"),
    required_permissions=["storage.write"],
)

register_tool(
    "gimp_image",
    CLIWrapperTool("gimp", "cli-anything-gimp"),
    required_permissions=["storage.write"],
)
```

---

## CLI-Anything Resources

- **GitHub:** https://github.com/HKUDS/CLI-Anything
- **Documentation:** 1,508 tests, 11 applications, 100% pass rate
- **Claude Code Plugin:** `/plugin marketplace add HKUDS/CLI-Anything`
- **Generated CLIs:**
  - `cli-anything-gimp` (107 tests)
  - `cli-anything-blender` (208 tests)
  - `cli-anything-libreoffice` (158 tests)
  - `cli-anything-shotcut` (154 tests)

---

## Use Case Analysis

### Scenario 1: PDF Generation (LibreOffice)

**MCP Approach:**
- Custom PDF generation service
- Direct API calls
- Requires development effort

**CLI-Anything Approach:**
- Auto-generated CLI: `cli-anything-libreoffice`
- Direct LibreOffice headless integration
- Proven (158 tests)
- Zero development effort

**Winner:** CLI-Anything

### Scenario 2: Email Integration

**MCP Approach:**
- Real-time email fetch
- Structured email schemas
- Built-in ACL
- Custom-built for AgentOS

**CLI-Anything Approach:**
- Wraps existing email CLI (mutt, neomutt)
- JSON output for email parsing
- No streaming (polling-based)
- Security via filesystem ACL

**Winner:** MCP

---

## Open Questions for Topic #21

1. **Universal Adapter Protocol:** Should we create a single `IntegrationAdapter` protocol that both MCP and CLI-Anything implement?

2. **Streaming Support:** Can we add streaming to CLI-Anything wrappers via subprocess line-by-line parsing?

3. **Security Unification:** How to apply AgentOS Gate 3 ACL to CLI-Anything tools (currently filesystem ACL only)?

4. **Tool Discovery:** Should CLI-Anything CLIs be auto-discovered or manually registered?

5. **Error Handling:** How to standardize error handling between MCP exceptions and CLI subprocess failures?

---

## Next Steps

1. **Continue Storage Service Design** (Topic #19) - Current focus
2. **Complete Topic #19** → Move to implementation planning
3. **Brainstorm Topic #20** (Projects/Spaces)
4. **Brainstorm Topic #21** (Universal Integration) → **Revisit MCP vs CLI-Anything here**

---

*Saved for later revisiting after Topic #21 universal integration layer design*
