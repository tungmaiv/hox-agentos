---
status: complete
phase: 02-agent-core-and-conversational-chat
source: 02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md, 02-05-SUMMARY.md
started: 2026-02-26T00:00:00Z
updated: 2026-02-26T09:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Chat sends a message and receives a streaming AI response
expected: Navigate to http://localhost:3000/chat. Type a message (e.g. "Hello, who are you?") and press Enter. The AI agent (blitz_master) should respond — text streams in progressively, not all at once. A final response appears in the chat panel.
result: pass
fixes: "Fixed 401 (token refresh in auth.ts), grey text (text-gray-900), focus loss (useMemo + callbacksRef), ValueError: No checkpointer set (MemorySaver on graph.compile)"

### 2. Conversation sidebar shows list and New Conversation button
expected: The left sidebar shows your past conversations (or is empty on first use). There is a "New Conversation" button at the top. Clicking it opens a fresh blank chat panel.
result: pass
fixes: "_save_memory_node missing contextvar fallback (conversations never saved); wrong env var BACKEND_URL → NEXT_PUBLIC_API_URL; added /api/conversations route + inProgress callback for dynamic refresh"

### 3. Conversation persists after page refresh
expected: Send a message and receive a response. Refresh the page (F5). The sidebar still shows that conversation. Clicking it loads the previous messages back into the chat panel.
result: pass
fixes: "agent/connect was using StateSnapshotEvent (doesn't populate chat list) — replaced with TextMessageStart/Content/End events per turn; rename textbox missing text-gray-900; localStorage title overrides for rename persistence; system prompt in master_agent.py to fix LLM LaTeX output"

### 4. Slash command /new starts a fresh conversation
expected: In the chat input, type "/new" and press Enter. The chat panel resets to an empty state (no messages). A new conversation entry appears in the sidebar. The "/new" text is NOT sent to the AI agent.
result: pass

### 5. Slash command /clear resets messages in current conversation
expected: After having some messages, type "/clear" in the input and press Enter. The messages in the chat panel disappear (cleared). The "/clear" text is NOT sent to the AI agent. The conversation still exists in the sidebar.
result: pass

### 6. Export conversation as markdown
expected: There is an export button (download icon) in the chat toolbar. Clicking it triggers a browser file download of a ".md" file containing the conversation messages formatted as markdown.
result: pass

### 7. Edit a sent message
expected: Hover over one of your sent (user) messages. A pencil/edit icon appears. Clicking it copies that message text back into the chat input field so you can modify and resend it.
result: pass

### 8. Custom instructions in /settings are respected by the agent
expected: Navigate to http://localhost:3000/settings. Type custom instructions in the textarea (e.g. "Always respond in Vietnamese."). Click Save. Return to chat, start a new conversation, send a message. The agent's response reflects your instructions (e.g. responds in Vietnamese).
result: pass
fixes: "settings page called /api/user/instructions/ directly (no Next.js proxy route → 404 silently); created proxy route; dark mode body CSS overriding settings page; removed prefers-color-scheme:dark from globals.css pre-MVP; math code blocks banned in system prompt"

### 9. Credentials API returns provider list without tokens
expected: Run: curl -H "Authorization: Bearer <token>" http://localhost:8000/api/credentials
Returns a JSON list of connected OAuth providers (e.g. [{"provider": "google", "connected_at": "..."}]). No token values, ciphertext, or sensitive data in the response.
result: pass
fixes: "curl multi-line paste breaks shell — ran directly via bash tool; /api/credentials redirects to /api/credentials/ (trailing slash)"

### 10. Conversations API returns user conversation list
expected: Run: curl -H "Authorization: Bearer <token>" http://localhost:8000/api/conversations/
Returns a JSON array of the user's conversations: [{conversation_id, title, last_message_at, message_count}]. The endpoint returns 401 without a valid Bearer token.
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps
