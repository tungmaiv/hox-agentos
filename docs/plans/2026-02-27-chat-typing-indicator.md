# Chat Typing Indicator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show an animated "Blitz is thinking…" bubble in the message thread while the agent is processing, so users know their message was received.

**Architecture:** Track `inProgress` as local React state in `ChatPanelInner`. Render a `TypingIndicator` component as an `absolute`-positioned overlay at the bottom of the chat container — it sits visually below the last message without touching CopilotKit's internal message list DOM. The indicator disappears the moment `inProgress` becomes `false`.

**Tech Stack:** React 18, TypeScript strict, Tailwind CSS, CopilotKit `onInProgress` callback (already wired).

---

### Task 1: Add `TypingIndicator` component and wire state

**Files:**
- Modify: `frontend/src/components/chat/chat-panel.tsx`

**Context to read first:**
Read `frontend/src/components/chat/chat-panel.tsx` lines 205–356 (`ChatPanelInner` and its return). The `handleInProgress` callback at line 214 already receives `inProgress: boolean` — we extend it to drive state. The outer `div` at line 316 is `flex flex-col h-full` — set it to `relative` so the overlay positions correctly.

---

**Step 1: Add `isProcessing` state to `ChatPanelInner`**

In `ChatPanelInner` (around line 206), add state after the existing `const { messages, reset }` line:

```typescript
const [isProcessing, setIsProcessing] = useState(false);
```

---

**Step 2: Wire `setIsProcessing` into `handleInProgress`**

The existing `handleInProgress` (lines 214–224) currently only refreshes the sidebar. Extend it to also track processing state:

```typescript
const handleInProgress = useCallback(
  (inProgress: boolean) => {
    setIsProcessing(inProgress);          // ← ADD THIS LINE
    if (inProgress) {
      wasInProgressRef.current = true;
    } else if (wasInProgressRef.current) {
      wasInProgressRef.current = false;
      onConversationUpdate?.();
    }
  },
  [onConversationUpdate]
);
```

`setIsProcessing` is stable (from `useState`) so it doesn't need to be in deps.

---

**Step 3: Add the `TypingIndicator` component**

Add this function component **above** `ChatPanelInner` (after the `EditableUserMessage` component, around line 194):

```typescript
function TypingIndicator() {
  return (
    <div className="flex items-end gap-2 px-4 pb-3">
      <div className="bg-white border border-gray-200 rounded-2xl px-4 py-2.5 shadow-sm flex items-center gap-1.5">
        <span className="text-xs text-gray-500 mr-1">Blitz is thinking</span>
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  );
}
```

---

**Step 4: Update the outer container and render the indicator**

In the `ChatPanelInner` return (line 316), the outer `div` is:
```tsx
<div className="flex flex-col h-full text-gray-900">
```

Add `relative` to it:
```tsx
<div className="flex flex-col h-full text-gray-900 relative">
```

Then render `TypingIndicator` as an absolutely-positioned overlay **between** the `CopilotChat` block and the end of the return. Replace the return block's closing structure:

```tsx
      <CopilotChat
        className="flex-1 min-h-0"
        {/* ...existing props unchanged... */}
      />

      {/* Typing indicator — overlays bottom of message thread while agent is processing */}
      {isProcessing && (
        <div className="absolute bottom-[60px] left-0 right-0 pointer-events-none">
          <TypingIndicator />
        </div>
      )}
    </div>
```

`bottom-[60px]` clears the input bar (which is ~60px tall). `pointer-events-none` prevents the overlay from blocking the Stop button.

---

**Step 5: Verify in browser**

Start the dev server:
```bash
just frontend
```

Open `http://localhost:3000/chat`.

1. Type any message and press Enter (or click Send)
2. **Expected:** The blue "Send" button disappears, the textarea is disabled, and a white bubble with "Blitz is thinking •••" appears just above the input bar
3. **Expected:** The bubble disappears the moment the first response token appears
4. **Expected:** The "Stop" button is still clickable (not blocked by the overlay)

---

**Step 6: Commit**

```bash
git add frontend/src/components/chat/chat-panel.tsx
git commit -m "feat(chat): add typing indicator bubble while agent is processing"
```
