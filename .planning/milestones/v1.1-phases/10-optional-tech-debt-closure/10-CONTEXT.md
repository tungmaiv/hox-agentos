# Phase 10: Optional Tech Debt Closure - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close 6 scoped tech debt items identified in the v1.1 milestone audit. No new features — all items are enforcement tightening, continuity wiring, test coverage, and documentation. Two plans:

- **10-01**: ChannelAdapter isinstance enforcement + channel LangGraph continuity + delivery_router unification
- **10-02**: UAT test 12 + Grafana alert live test + Phase 4.1 VERIFICATION.md

</domain>

<decisions>
## Implementation Decisions

### ChannelAdapter isinstance enforcement (Plan 10-01)
- Add a `register_adapter(name: str, adapter: ChannelAdapter)` method on `ChannelGateway`
- Raise `TypeError` immediately at `register_adapter()` call time if `not isinstance(adapter, ChannelAdapter)`
- Do NOT break the existing URL-based sidecar mechanism (`sidecar_urls` dict) — it stays as-is
- The check is additive: any future Python-level adapter registration gets validated at startup
- One test verifying the `TypeError` on a non-conforming object is sufficient

### Channel LangGraph continuity (Plan 10-01)
- Use a module-level dict `_channel_graph_savers: dict[str, MemorySaver]` in `gateway.py`
- Key is `str(conversation_id)` — same `conversation_id` that already flows via `ChannelSession`
- `_invoke_agent()` looks up or creates a `MemorySaver` keyed by `conversation_id`, then passes it to `create_master_graph(checkpointer=saver)` — same saver reused across calls for the same session
- Do NOT switch to `AsyncPostgresSaver` — MemorySaver cached per-session is sufficient at 100-user scale and avoids new DB dependency
- Session memory stays alive as long as the Python process lives (acceptable for dev/single-node MVP)
- Existing `ConversationTurn` PostgreSQL persistence is kept unchanged — both mechanisms coexist

### delivery_router unification (Plan 10-01)
- In `_invoke_agent()`, set `initial_state["delivery_targets"] = [msg.channel.upper()]` before calling `graph.ainvoke()`
- This routes the response through `delivery_router_node` in the graph, which already handles TELEGRAM/WHATSAPP/TEAMS via `DeliveryTarget` enum
- `_invoke_agent()` return type changes from `InternalMessage` to `None` — the graph delivers directly via the sidecar
- `handle_inbound()` no longer needs to extract AI response text and call `send_outbound()` separately — remove that post-processing step
- If `msg.channel == "web"` is ever passed (shouldn't happen), delivery_router handles WEB_CHAT transparently

### UAT test 12: Admin Create Skill via API (Plan 10-02)
- Add `test_uat_12_admin_create_skill` in `tests/test_phase6_integration.py` alongside existing UAT tests
- Coverage: POST /api/admin/skills (admin JWT) → 201 response with `id` — skill is retrievable via GET /api/admin/skills/{id}
- Include at least one error case: POST without admin role → 403
- Follow existing UAT test pattern in the file (numbered comment header, assert status codes, assert body fields)
- Does NOT need to invoke the skill at runtime — creation + retrieval is sufficient for this UAT

### Grafana → Telegram alert live test (Plan 10-02)
- Procedure: temporarily lower `blitz_llm_spend_alert` threshold in `infra/grafana/provisioning/alerting/alert_rules.yml` below current accumulated spend → wait one evaluation cycle (default 1m) → verify Telegram message arrives in the ops channel → restore threshold
- Document the test result in `10-02-SUMMARY.md` as evidence (timestamp, threshold used, message received)
- No permanent config changes — threshold is restored after test
- If Grafana/LiteLLM metrics are not in a state where a real breach is triggerable, do a no-op spend event via the test suite to cross the threshold instead

### Phase 4.1 VERIFICATION.md (Plan 10-02)
- Create `.planning/phases/04.1-phase4-polish/04.1-VERIFICATION.md`
- Contains both Phase 4.1 success criteria (from ROADMAP.md) with SATISFIED status
- Evidence drawn from `04.1-01-SUMMARY.md` (already present) — no re-verification needed
- Follow the standard VERIFICATION.md format used in other phases

### Claude's Discretion
- Exact test fixture/mock approach for UAT test 12 (use existing conftest patterns)
- How to clean up stale `_channel_graph_savers` entries (can skip for now at 100-user scale)
- Whether to add a `saver_cleanup_after_idle_hours` config — skip for MVP

</decisions>

<specifics>
## Specific Ideas

- The `MemorySaver` dict approach is explicitly chosen over `AsyncPostgresSaver` — simpler, no migration, acceptable at single-node scale
- delivery_router unification should result in fewer code paths: `_invoke_agent()` becomes fire-and-forget (None return) and `handle_inbound()` response extraction block can be deleted
- UAT test 12 numbering should match the sequential test numbering already in the integration test file

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-optional-tech-debt-closure*
*Context gathered: 2026-03-02*
