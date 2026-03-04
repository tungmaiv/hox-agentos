# Excalidraw Diagram Agent — Design Proposal

> **Date:** 2026-02-28
> **Status:** Proposal
> **Approach:** LLM-native JSON generation (Approach A)

## 1. Overview

A LangGraph sub-agent for Blitz AgentOS that converts natural language descriptions,
Mermaid syntax, or ASCII art into interactive Excalidraw diagrams. Users invoke it
from the Blitz chat UI; the agent generates, validates, previews, and iteratively
refines diagrams before exporting.

### Requirements

| Requirement | Detail |
|-------------|--------|
| Input formats | Natural language, Mermaid syntax, ASCII art |
| Output formats | Inline SVG preview + `.excalidraw` file download + shareable excalidraw.com URL |
| Architecture | LangGraph sub-agent with iterative refinement loop |
| Integration | Registered in `tool_registry.py`, hands off from `master_agent` |
| Security | Standard 3-gate security (JWT + RBAC + Tool ACL) |

---

## 2. Why Approach A (LLM-Native JSON)

Three approaches were evaluated:

| Approach | Description | Verdict |
|----------|-------------|---------|
| **A: LLM-native JSON** | LLM generates Excalidraw JSON directly | **Chosen** — single code path, pure Python, handles all diagram types |
| B: Mermaid-first pipeline | Convert all input to Mermaid, then to Excalidraw via `@excalidraw/mermaid-to-excalidraw` | Rejected — requires Node.js, limited to flowcharts for full fidelity |
| C: Hybrid | Mermaid for structured input, LLM for creative | Rejected — two code paths, classification complexity |

Key advantages of Approach A:
- **Universality** — handles ANY diagram type, not just Mermaid-supported ones
- **Simplicity** — single code path, pure Python, no Node.js dependency
- **Natural iteration** — the LLM edits its own JSON output conversationally
- **Fits Blitz architecture** — stays in the Python/LangGraph ecosystem
- **Validation catches errors** — Pydantic schema validates Excalidraw JSON before rendering

---

## 3. Sub-Agent Architecture

```
User: "Draw a flowchart of our auth flow"
        |
        v
+-------------------+
|  Master Agent     |  <- detects diagram intent
|  (blitz_master)   |
+--------+----------+
         | handoff
         v
+-----------------------------------------------+
|  Diagram Agent (diagram_agent)                |
|                                               |
|  State: DiagramState(TypedDict)               |
|                                               |
|  Nodes:                                       |
|    classify -> generate -> validate --+       |
|                    ^                  |       |
|                    |  fix             v       |
|                    +------------ valid? -> present
|                                           |
|                                 refine <--+
|                                               |
|  Tools:                                       |
|    - validate_excalidraw                      |
|    - render_preview (JSON -> SVG)             |
|    - export_file (.excalidraw save)           |
|    - generate_share_url (excalidraw.com link) |
+-----------------------------------------------+
```

### Registration

```python
# gateway/tool_registry.py
"diagram.generate": ToolSpec(
    handler=diagram_agent.run,
    required_permissions=["diagram:create"],
    description="Generate Excalidraw diagrams from text, Mermaid, or ASCII",
)
```

---

## 4. DiagramState

```python
class DiagramState(TypedDict):
    # Input
    input_text: str                                  # Raw user input
    input_type: Literal["mermaid", "ascii", "nl"]    # Classified input format

    # Generation
    elements: list[dict]                             # Excalidraw elements array
    app_state: dict                                  # Excalidraw appState
    files: dict                                      # Excalidraw files dict (empty for now)

    # Iteration control
    validation_errors: list[str]                     # Current validation issues
    retry_count: int                                 # Auto-fix attempts (max 3)
    revision_count: int                              # User-requested refinements (max 10)
    user_feedback: str | None                        # Latest refinement request

    # Output
    preview_svg: str | None                          # Inline SVG for chat
    file_path: str | None                            # Saved .excalidraw file path
    share_url: str | None                            # excalidraw.com link
    status: Literal["generating", "validating", "presenting", "refining", "done", "error"]
```

---

## 5. Node Flow (6 Nodes)

### Node 1: `classify`

Detects input type via regex + heuristics (no LLM call needed).

```python
def _classify(text: str) -> Literal["mermaid", "ascii", "nl"]:
    stripped = text.strip()
    # Mermaid: starts with known diagram keywords
    mermaid_keywords = [
        "graph ", "flowchart ", "sequenceDiagram", "classDiagram",
        "stateDiagram", "erDiagram", "gantt", "pie ", "gitGraph",
    ]
    if any(stripped.startswith(kw) for kw in mermaid_keywords):
        return "mermaid"
    # ASCII: high ratio of box-drawing / structural chars
    box_chars = set("+-|/\\>*=[]{}|+-|/\\>*=")
    ratio = sum(1 for c in stripped if c in box_chars) / max(len(stripped), 1)
    if ratio > 0.15:
        return "ascii"
    return "nl"
```

### Node 2: `generate`

LLM call using `blitz/master`. System prompt contains:
- Condensed Excalidraw schema reference (~2000 tokens)
- Layout guidelines (spacing, alignment, z-ordering)
- Input-type-specific context
- Output contract: return `{"elements": [...], "appState": {...}}` only

### Node 3: `validate`

Runs Pydantic-based structural validation:

1. Every element has required base fields (id, type, x, y, width, height, seed, version)
2. All IDs are unique
3. Bidirectional bindings are consistent:
   - `arrow.startBinding.elementId` -> that element's `boundElements` includes arrow ID
   - `text.containerId` -> that container's `boundElements` includes text ID
4. No overlapping shapes (bounding box collision detection with tolerance)
5. Element types are valid Excalidraw types
6. `points` arrays on arrows/lines have >= 2 points, first is `[0, 0]`

Returns `list[str]` of error messages (empty = valid).

### Node 4: `fix`

If validation fails and `retry_count < 3`: LLM receives the current JSON + error list,
returns corrected JSON. Loops back to `validate`.

If `retry_count >= 3`: transitions to `error` status with the validation errors surfaced to the user.

### Node 5: `present`

1. Calls `render_preview` tool -> SVG string
2. Calls `export_file` tool -> saved `.excalidraw` file path
3. Calls `generate_share_url` tool -> excalidraw.com URL
4. Emits A2UI envelopes to the chat
5. Waits for user response: "done" -> export node, or feedback -> refine node

### Node 6: `refine`

LLM receives: current elements JSON + user feedback string.
Returns: modified elements JSON. Loops back to `validate`.

Increments `revision_count`. Max 10 refinements per session.

---

## 6. Tools

### 6.1 `validate_excalidraw`

Pure Python. Pydantic models for each element type validate structure.
Returns list of error strings.

### 6.2 `render_preview`

Simple Python SVG renderer. Maps Excalidraw elements to SVG primitives:

| Excalidraw type | SVG element |
|----------------|-------------|
| `rectangle` | `<rect>` |
| `ellipse` | `<ellipse>` |
| `diamond` | `<polygon>` (rotated square) |
| `text` | `<text>` |
| `arrow` | `<line>` + `<polygon>` arrowhead marker |
| `line` | `<polyline>` |
| `frame` | `<rect>` with dashed stroke |

Applies strokeColor, backgroundColor, strokeWidth, opacity.
Skips roughness/hand-drawn effect (preview only — full fidelity in Excalidraw app).

### 6.3 `export_file`

Assembles the full `.excalidraw` JSON and saves it:

```python
# Save path: /tmp/blitz-diagrams/{user_id}/{uuid}.excalidraw
# File structure:
{
    "type": "excalidraw",
    "version": 2,
    "source": "blitz-agentos",
    "elements": [...],   # from state
    "appState": {
        "viewBackgroundColor": "#ffffff",
        "gridSize": 20
    },
    "files": {}
}
```

### 6.4 `generate_share_url`

Excalidraw supports loading diagrams via URL hash:

```
https://excalidraw.com/#json={base64_encoded_json}
```

Base64-encodes the JSON and constructs the URL.
For large diagrams exceeding URL length limits (~2000 chars), falls back to file download only.

---

## 7. Excalidraw Schema Prompt Reference

The system prompt for `generate` and `refine` nodes includes a condensed schema reference.

### Element Type Catalog

| Type | Shape | Key extra fields |
|------|-------|-----------------|
| `rectangle` | Box | `roundness: {type: 3}` for rounded corners |
| `ellipse` | Oval | (none) |
| `diamond` | Diamond | (none) |
| `text` | Label | `text`, `fontSize`, `fontFamily`, `containerId`, `textAlign`, `verticalAlign` |
| `arrow` | Connector | `points`, `startBinding`, `endBinding`, `startArrowhead`, `endArrowhead` |
| `line` | Line | `points` |
| `frame` | Group frame | `name` |

### Binding Rules

**Arrow-to-Shape (bidirectional):**
1. Arrow gets `startBinding` / `endBinding` with `{elementId, focus, gap, fixedPoint}`
2. Source shape adds `{id: arrowId, type: "arrow"}` to `boundElements`
3. Target shape adds `{id: arrowId, type: "arrow"}` to `boundElements`

**Text-to-Container (bidirectional):**
1. Text element sets `containerId` to parent shape ID
2. Container shape adds `{id: textId, type: "text"}` to `boundElements`

### `fixedPoint` coordinates (arrow attachment points)

| Position | Value |
|----------|-------|
| Left edge center | `[0.0, 0.5001]` |
| Right edge center | `[1.0, 0.5001]` |
| Top edge center | `[0.5001, 0.0]` |
| Bottom edge center | `[0.5001, 1.0]` |

Use `0.5001` instead of `0.5` to avoid floating-point precision issues.

### Layout Guidelines

| Layout | Horizontal spacing | Vertical spacing | Arrow width |
|--------|-------------------|-------------------|-------------|
| Left-to-right | 200px between nodes | — | 140px |
| Top-down | — | 150px between nodes | — |
| Grid | 200px columns | 150px rows | varies |

**Z-order:** shapes first -> text -> arrows last (front).

### Color Palette (Excalidraw defaults)

| Color | Hex | Use |
|-------|-----|-----|
| Blue | `#a5d8ff` | Primary/input nodes |
| Green | `#b2f2bb` | Success/output nodes |
| Yellow | `#ffec99` | Warning/decision nodes |
| Red | `#ffc9c9` | Error/danger nodes |
| Purple | `#d0bfff` | External/API nodes |
| Orange | `#ffd8a8` | Queue/async nodes |
| Gray | `#dee2e6` | Utility/helper nodes |
| White | `#ffffff` | Default background |

### Diagram Type Heuristics

When input is NL, the LLM chooses layout based on content:

| Detected concept | Layout | Shapes |
|-----------------|--------|--------|
| Process/workflow/flow | Left-to-right horizontal | Rectangles + arrows |
| Decision tree | Top-down vertical | Rectangles + diamonds + arrows |
| Architecture/system | Free-form clustered | Rectangles (grouped) + arrows |
| Entity relationships | Grid layout | Rectangles + labeled arrows |
| Sequence/timeline | Vertical lanes | Rectangles + dashed arrows |
| Hierarchy/org chart | Top-down tree | Rectangles + straight arrows |

---

## 8. Frontend Integration (A2UI)

The sub-agent emits A2UI envelopes:

```jsonl
{"type": "diagram_preview", "svg": "<svg>...</svg>"}
{"type": "diagram_file", "url": "/api/files/{file_id}", "filename": "auth-flow.excalidraw"}
{"type": "diagram_share", "url": "https://excalidraw.com/#json=..."}
{"type": "diagram_prompt", "message": "Here's your diagram. Want any changes?"}
```

The frontend `A2UIMessageRenderer` gets a new case for `diagram_preview` that renders:
- Inline SVG diagram
- "Download .excalidraw" button
- "Open in Excalidraw" link
- "Refine" input field for iteration

---

## 9. Master Agent Handoff

```python
# In master_agent.py router node:
DIAGRAM_KEYWORDS = [
    "draw", "diagram", "flowchart", "architecture diagram",
    "sequence diagram", "er diagram", "mind map", "sketch",
    "visualize", "graph TD", "graph LR", "sequenceDiagram",
]
# if any keyword in user_message -> handoff to diagram_agent
# diagram_agent returns -> master_agent presents result in chat
```

---

## 10. File Structure (New Files)

```
backend/
  agents/
    subagents/
      diagram_agent.py          # LangGraph sub-agent (state, nodes, graph)
  tools/
    diagram_tools.py            # validate, render_preview, export, share_url
  core/
    schemas/
      excalidraw.py             # Pydantic models for Excalidraw element types
```

---

## 11. Security & Limits

| Concern | Mitigation |
|---------|-----------|
| Authentication | Standard 3-gate: JWT -> RBAC -> Tool ACL |
| File isolation | User-scoped temp dir: `/tmp/blitz-diagrams/{user_id}/` |
| Credential exposure | None — purely generative tool, no credentials involved |
| LLM cost control | Rate limit: max 20 diagram generations per user per hour |
| Infinite loops | Max 3 auto-fix retries, max 10 user refinements per session |
| Large diagrams | URL share fallback to file-only when base64 exceeds ~2000 chars |

---

## 12. Excalidraw JSON Reference (Complete Example)

Two connected boxes with labels — the minimum viable connected diagram:

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "blitz-agentos",
  "elements": [
    {
      "id": "box1",
      "type": "rectangle",
      "x": 100, "y": 100,
      "width": 160, "height": 80,
      "angle": 0,
      "strokeColor": "#1e1e1e",
      "backgroundColor": "#a5d8ff",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "strokeStyle": "solid",
      "roughness": 1,
      "opacity": 100,
      "seed": 1234567890,
      "version": 1,
      "versionNonce": 987654321,
      "isDeleted": false,
      "groupIds": [],
      "frameId": null,
      "roundness": { "type": 3 },
      "boundElements": [
        { "id": "label1", "type": "text" },
        { "id": "arrow1", "type": "arrow" }
      ],
      "link": null,
      "locked": false,
      "updated": 1700000000000
    },
    {
      "id": "label1",
      "type": "text",
      "x": 130, "y": 125,
      "width": 100, "height": 30,
      "angle": 0,
      "strokeColor": "#1e1e1e",
      "backgroundColor": "transparent",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "strokeStyle": "solid",
      "roughness": 0,
      "opacity": 100,
      "seed": 1111111111,
      "version": 1,
      "versionNonce": 2222222222,
      "isDeleted": false,
      "groupIds": [],
      "frameId": null,
      "roundness": null,
      "boundElements": null,
      "link": null,
      "locked": false,
      "updated": 1700000000000,
      "text": "Input",
      "fontSize": 20,
      "fontFamily": 1,
      "textAlign": "center",
      "verticalAlign": "middle",
      "containerId": "box1",
      "originalText": "Input",
      "autoResize": true,
      "lineHeight": 1.25
    },
    {
      "id": "box2",
      "type": "rectangle",
      "x": 400, "y": 100,
      "width": 160, "height": 80,
      "angle": 0,
      "strokeColor": "#1e1e1e",
      "backgroundColor": "#b2f2bb",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "strokeStyle": "solid",
      "roughness": 1,
      "opacity": 100,
      "seed": 3333333333,
      "version": 1,
      "versionNonce": 4444444444,
      "isDeleted": false,
      "groupIds": [],
      "frameId": null,
      "roundness": { "type": 3 },
      "boundElements": [
        { "id": "label2", "type": "text" },
        { "id": "arrow1", "type": "arrow" }
      ],
      "link": null,
      "locked": false,
      "updated": 1700000000000
    },
    {
      "id": "label2",
      "type": "text",
      "x": 430, "y": 125,
      "width": 100, "height": 30,
      "angle": 0,
      "strokeColor": "#1e1e1e",
      "backgroundColor": "transparent",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "strokeStyle": "solid",
      "roughness": 0,
      "opacity": 100,
      "seed": 5555555555,
      "version": 1,
      "versionNonce": 6666666666,
      "isDeleted": false,
      "groupIds": [],
      "frameId": null,
      "roundness": null,
      "boundElements": null,
      "link": null,
      "locked": false,
      "updated": 1700000000000,
      "text": "Process",
      "fontSize": 20,
      "fontFamily": 1,
      "textAlign": "center",
      "verticalAlign": "middle",
      "containerId": "box2",
      "originalText": "Process",
      "autoResize": true,
      "lineHeight": 1.25
    },
    {
      "id": "arrow1",
      "type": "arrow",
      "x": 260, "y": 140,
      "width": 140, "height": 0,
      "angle": 0,
      "strokeColor": "#1e1e1e",
      "backgroundColor": "transparent",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "strokeStyle": "solid",
      "roughness": 1,
      "opacity": 100,
      "seed": 7777777777,
      "version": 1,
      "versionNonce": 8888888888,
      "isDeleted": false,
      "groupIds": [],
      "frameId": null,
      "roundness": { "type": 2 },
      "boundElements": null,
      "link": null,
      "locked": false,
      "updated": 1700000000000,
      "points": [[0, 0], [140, 0]],
      "startArrowhead": null,
      "endArrowhead": "arrow",
      "startBinding": {
        "elementId": "box1",
        "focus": 0,
        "gap": 5,
        "fixedPoint": [1.0, 0.5001]
      },
      "endBinding": {
        "elementId": "box2",
        "focus": 0,
        "gap": 5,
        "fixedPoint": [0.0, 0.5001]
      }
    }
  ],
  "appState": {
    "viewBackgroundColor": "#ffffff",
    "gridSize": 20
  },
  "files": {}
}
```

---

## 13. Open Questions (For Implementation Planning)

1. **Temp file cleanup** — Cron job or TTL-based cleanup for `/tmp/blitz-diagrams/`? Suggest 24h TTL.
2. **Image support** — Excalidraw supports embedded images (`type: "image"` + `files` dict). Defer to v2?
3. **Collaborative editing** — Should the share URL use Excalidraw's collaboration mode? Defer to v2.
4. **Mermaid fallback** — If LLM struggles with complex Mermaid syntax, add `@excalidraw/mermaid-to-excalidraw` as optional Node.js sidecar? Evaluate after MVP.
