# Chat Typing Indicator — Design

**Date:** 2026-02-27
**Status:** Approved

## Problem

When a user sends a message in the chat window, the input clears and is disabled, but nothing appears in the message thread to indicate the agent is working. Users have no visual feedback that their message was received and a response is coming.

## Solution

Add a typing indicator bubble that appears at the bottom of the message thread while the agent is processing (`inProgress === true`). It disappears the moment the first response token arrives.

## Design

### Visual

- Left-aligned bubble matching the assistant message style (white background, rounded corners)
- Content: grey text "Blitz is thinking…" + three pulsing dots (`animate-pulse`)
- Visible only while `inProgress === true`

### Implementation

**File:** `frontend/src/components/chat/chat-panel.tsx`

1. Add `const [isProcessing, setIsProcessing] = useState(false)` to `ChatPanelInner`
2. Update `handleInProgress` to also call `setIsProcessing(inProgress)` in addition to its existing sidebar-refresh logic
3. Add a `TypingIndicator` component (defined in the same file) that renders the animated bubble
4. Render `TypingIndicator` as an absolutely-positioned overlay at the bottom of the chat flex container, below `CopilotChat` — avoids touching CopilotKit's internal message list DOM

### Why overlay positioning

CopilotKit's `CopilotChat` owns the message list DOM. An `absolute bottom` overlay achieves the same visual result (indicator appears below the last message) with no risk of breaking CopilotKit internals.

### Edge case

When `inProgress` becomes `false`, the indicator disappears immediately — even before the full response is rendered. This is acceptable because the first streaming token renders simultaneously.

## Files Changed

- `frontend/src/components/chat/chat-panel.tsx` — only file touched
