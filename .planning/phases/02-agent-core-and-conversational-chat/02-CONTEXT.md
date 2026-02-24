# Phase 2: Agent Core and Conversational Chat - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can have a natural language conversation with a streaming AI agent (Blitz) that remembers the conversation, routes LLM calls through LiteLLM Proxy using model aliases, and has isolated per-user memory. This phase delivers the conversational core: master agent (LangGraph), AG-UI streaming chat UI, short-term conversation memory, encrypted credential store, and OAuth connections for Google and Microsoft. Sub-agents, long-term memory, tools, canvas, and channels are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Chat UI Layout & Structure
- Sidebar + main layout: conversation list on the left, chat panel on the right
- Mobile: sidebar collapses to a hamburger menu — chat takes full width
- Agent identified by name ("Blitz") and a small avatar icon in the chat
- No agent status badge — streaming and loading states communicate status implicitly

### Message Display
- Bubble style: user messages on the right, agent messages on the left
- Full markdown rendering: headers, bold, italic, lists, inline code, tables
- Syntax-highlighted code blocks with a Copy button on each block
- Copy icon appears on hover on each agent message bubble
- Agent response streams into a single bubble that builds in place as tokens arrive (no placeholder-replace pattern)

### Streaming & Interaction
- Tokens stream in real-time as they arrive (AG-UI streaming)
- Stop Generation button visible while agent is generating
- User messages have an Edit icon — clicking allows modifying and resending
- Enter to send, Shift+Enter for new line in the input box
- Inline error message with a Retry button when LLM call fails mid-stream

### Chat Input Capabilities
- File upload supported — agent reads file contents
- Image paste supported — pasted images sent to the multimodal model (blitz/master)
- No @ mention support in Phase 2 (deferred to Phase 3 with sub-agents)
- Slash commands: `/new` starts a new conversation, `/clear` clears the current context window

### Agent Thinking Visibility
- Collapsible "Thinking..." section displayed above the final response when the agent reasons
- Tool calls shown inline with name + status ("🔧 Fetching email...") — collapses automatically when the tool completes
- When sub-agents run in parallel (Phase 3+): show which sub-agent is active (e.g. "📧 Email Agent working...")
- No feedback buttons (thumbs up/down) in Phase 2
- Export full conversation as markdown — available via a button in the chat

### Conversation Management
- Auto-named from the first user message (like ChatGPT)
- Rename and delete both available via context menu (⋮ or right-click) on each conversation in sidebar
- Sidebar shows last 20 conversations with scroll/pagination for older ones
- Relative timestamps shown in sidebar (e.g. "2 hours ago")
- App opens to most recent conversation by default
- Prominent "New Conversation" button at top of sidebar
- Load last 20 turns into agent context window; Phase 3 adds summarization for older turns
- Older messages in a conversation lazy-load as user scrolls up

### Agent Persona & Tone
- Professional but warm — smart colleague, not a robot. Helpful and clear, occasionally light in tone
- When user asks something outside current capabilities: acknowledge the gap honestly, explain what Blitz can currently do
- New conversation starts with a brief welcome message from Blitz including 2–3 example prompts
- Users can add custom instructions (like ChatGPT custom instructions) — stored per user, appended to system prompt

### Credential Connection Flow
- Dedicated `/settings/connections` page (not inline modal in Phase 2)
- Phase 2 connects Google (Gmail + Google Calendar) and Microsoft (Outlook + Teams) via OAuth
- Success state: green checkmark + "Connected" label next to the provider
- Token refresh: auto-refresh via refresh token silently; show a reconnect banner in the UI if refresh fails

### LiteLLM Model Visibility
- Model routing is invisible and admin-controlled — no model switcher for users
- If shown at all, display alias only (e.g. "blitz/master") — never expose provider model names
- Fallbacks are transparent — no user notification when LiteLLM routes to a fallback model
- No cost or token usage display in Phase 2 (deferred to Phase 8 Observability)

### Claude's Discretion
- Character/token limit indicator on the input box (no strong preference — keep it minimal)
- Exact progress bar or loading skeleton designs
- Spacing, typography, and exact color choices for the chat UI
- Compression algorithm and temp file handling for file uploads
- Exact system prompt wording for Blitz persona
- How to handle photos or files with ambiguous types on upload

</decisions>

<specifics>
## Specific Ideas

- The chat should feel like a polished internal tool — not a demo. Reference: Claude.ai layout but with the Blitz brand
- Blitz is not just a chatbot — it's the entry point to an agentic OS. The "Thinking..." and tool status patterns set the foundation for Phase 3's richer agent behaviors; implement them robustly in Phase 2
- Custom instructions are important — the user specifically called this out as a feature for Phase 2 (not deferred)
- The welcome message with example prompts should change or be curated based on what Phase 2 actually supports (conversation, reasoning, document reading) — don't promise email/calendar features not yet built
- File upload in Phase 2 means reading file contents as context, not storing files permanently

</specifics>

<deferred>
## Deferred Ideas

- @ mention support to route to sub-agents — Phase 3 (when sub-agents exist)
- Feedback mechanism (thumbs up/down) on messages — later phase when feedback storage is built
- Agent status badge (online/processing/idle) — not needed; re-evaluate in Phase 3 if complexity increases
- Per-user model selection (blitz/master vs blitz/fast dropdown) — re-evaluate post-MVP
- Cost/token usage display — Phase 8 (Observability with Grafana + LiteLLM cost tracking)
- Search/filter conversations — backlog
- Conversation pinning or folders — backlog
- Voice input — post-MVP

</deferred>

---

*Phase: 02-agent-core-and-conversational-chat*
*Context gathered: 2026-02-25*
