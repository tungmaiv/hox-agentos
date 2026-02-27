// frontend/src/components/chat/chat-panel.tsx
"use client";
/**
 * ChatPanel — streaming chat with CopilotKit AG-UI protocol.
 *
 * CRITICAL: agent name MUST be 'blitz_master' — this must match
 * the LangGraphAgent name registered in backend/gateway/runtime.py.
 *
 * CRITICAL: runtimeUrl='/api/copilotkit' — this must match the registered
 * Next.js route at frontend/src/app/api/copilotkit/route.ts.
 *
 * threadId=conversationId — CopilotKit sends this as 'threadId' in the
 * AG-UI request body. The backend (gateway/runtime.py) extracts it and
 * sets current_conversation_id_ctx to scope memory operations.
 *
 * Focus stability:
 *   CustomInput and CustomUserMessage are created with useMemo(()=>..., []).
 *   Creating component types inside a render function causes CopilotChat to
 *   unmount + remount the input on every keystroke (new type reference = full
 *   remount = focus lost). Stable references prevent this.
 *   Callbacks are accessed via callbacksRef so the memoized closures always
 *   call the latest function without needing deps.
 *
 * Edit message:
 *   editEventRef holds a setter registered by SlashCommandInput on mount.
 *   Clicking the pencil icon calls editEventRef.current(text) directly,
 *   updating the input value without re-rendering ChatPanelInner at all.
 */
import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { CopilotKit, useCopilotChatInternal } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import type { InputProps, UserMessageProps, AssistantMessageProps } from "@copilotkit/react-ui";
import { A2UIMessageRenderer } from "@/components/a2ui";

/** Minimal Message shape for export serialization (role + content fields from AG-UI). */
interface ChatMessage {
  role: string;
  content?: string | unknown;
}

interface ChatPanelProps {
  conversationId: string | null;
  onSidebarToggle: () => void;
  onNewConversation: () => void;
  onConversationUpdate?: () => void;
}

const BLITZ_WELCOME_MESSAGE = `Hi! I'm Blitz, your AI assistant. I can help you with:

- **Answering questions** and reasoning through complex topics
- **Analyzing documents** you upload or paste
- **Writing and editing** — drafts, summaries, rewrites
- **Coding help** — debugging, explanations, code review

What would you like to work on?`;

const SYSTEM_PROMPT = `You are Blitz, an intelligent AI assistant for Blitz employees. You are professional but warm — like a smart, helpful colleague. You are clear, direct, and occasionally light in tone.

When asked about capabilities: Be honest. In this phase you can reason, answer questions, read uploaded documents, and help with writing and coding. You cannot yet fetch emails, check calendars, or query projects — those capabilities are coming soon.

When you don't know something: Say so directly. Don't make up information.

Format your responses with markdown when it improves clarity (headers, bold, code blocks). Keep responses focused and appropriately concise. For math, write calculations in plain text (e.g. "1234 × 2345 = 2,894,030") — do not use LaTeX notation.`;

// ---------------------------------------------------------------------------
// Custom Input component — intercepts slash commands before sending
// ---------------------------------------------------------------------------
interface SlashInputProps extends InputProps {
  onNewConversation: () => void;
  onClearMessages: () => void;
  /** Ref whose .current is set by this component on mount so the parent can
   *  imperatively push a new input value (e.g. from "Edit message" click). */
  editEventRef: React.MutableRefObject<((text: string) => void) | null>;
}

function SlashCommandInput({
  onSend,
  inProgress,
  onStop,
  onNewConversation,
  onClearMessages,
  editEventRef,
}: SlashInputProps) {
  const [inputValue, setInputValue] = useState("");

  // Register edit handler — lets parent push a value into this input imperatively
  // without a re-render cascade that would lose focus.
  useEffect(() => {
    editEventRef.current = (text: string) => setInputValue(text);
    return () => {
      editEventRef.current = null;
    };
  }, [editEventRef]);

  const handleSlashCommand = (value: string): boolean => {
    const trimmed = value.trim();
    if (trimmed === "/new") {
      onNewConversation();
      return true;
    }
    if (trimmed === "/clear") {
      onClearMessages();
      return true;
    }
    return false;
  };

  const handleKeyDown = async (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!inputValue.trim() || inProgress) return;
      if (handleSlashCommand(inputValue)) {
        setInputValue("");
        return;
      }
      const text = inputValue;
      setInputValue("");
      await onSend(text);
    }
  };

  return (
    <div className="flex items-end gap-2 p-3 border-t border-gray-200 bg-white text-gray-900">
      <textarea
        className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[44px] max-h-40"
        placeholder="Ask anything... (Enter to send, Shift+Enter for new line, /new for new chat, /clear to clear)"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        disabled={inProgress}
      />
      <div className="flex flex-col gap-1">
        {inProgress ? (
          <button
            onClick={onStop}
            className="px-3 py-2 bg-red-100 hover:bg-red-200 text-red-700 text-xs font-medium rounded-lg transition-colors"
            aria-label="Stop generation"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={async () => {
              if (!inputValue.trim()) return;
              if (handleSlashCommand(inputValue)) {
                setInputValue("");
                return;
              }
              const text = inputValue;
              setInputValue("");
              await onSend(text);
            }}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors"
            aria-label="Send message"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom UserMessage component — shows Edit icon on hover
// ---------------------------------------------------------------------------
interface EditableUserMessageProps extends UserMessageProps {
  onEdit: (text: string) => void;
}

function EditableUserMessage({ message, onEdit }: EditableUserMessageProps) {
  const content =
    message && typeof message.content === "string" ? message.content : "";
  return (
    <div className="group relative flex justify-end mb-2 px-3">
      <div className="bg-blue-600 text-white rounded-2xl px-4 py-2 max-w-[80%] text-sm whitespace-pre-wrap">
        {content}
      </div>
      {content && (
        <button
          className="absolute -top-2 right-2 opacity-0 group-hover:opacity-100 bg-white border border-gray-200 rounded-full w-6 h-6 flex items-center justify-center text-gray-500 hover:text-gray-700 shadow-sm transition-opacity text-xs"
          onClick={() => onEdit(content)}
          aria-label="Edit message"
          title="Edit and resend"
        >
          &#9998;
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Typing indicator — animated dots while agent is processing
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Inner panel — must be inside CopilotKit context to use hooks
// ---------------------------------------------------------------------------
interface ChatPanelInnerProps {
  conversationId: string;
  onSidebarToggle: () => void;
  onNewConversation: () => void;
  onConversationUpdate?: () => void;
}

function ChatPanelInner({ conversationId, onSidebarToggle, onNewConversation, onConversationUpdate }: ChatPanelInnerProps) {
  const { messages, reset } = useCopilotChatInternal();
  const [isProcessing, setIsProcessing] = useState(false);

  // History is restored via agent/connect StateSnapshot (runtime.py loads turns
  // from DB and returns them in the snapshot). No client-side fetch needed.

  // Detect inProgress true → false transition to refresh the sidebar after
  // the AI finishes responding (save_memory has run by then on the backend).
  const wasInProgressRef = useRef(false);
  const handleInProgress = useCallback(
    (inProgress: boolean) => {
      setIsProcessing(inProgress);
      if (inProgress) {
        wasInProgressRef.current = true;
      } else if (wasInProgressRef.current) {
        wasInProgressRef.current = false;
        onConversationUpdate?.();
      }
    },
    [onConversationUpdate]
  );

  // editEventRef: set by SlashCommandInput on mount; called to push text into the input.
  const editEventRef = useRef<((text: string) => void) | null>(null);

  // Callback refs — updated every render so memoized components always call the
  // latest version of each callback without needing to be recreated themselves.
  const callbacksRef = useRef({ onNewConversation, reset });
  callbacksRef.current.onNewConversation = onNewConversation;
  callbacksRef.current.reset = reset;

  // Stable component type references — created once, never recreated on re-render.
  // useMemo(()=>..., []) guarantees the same function identity every render, so
  // CopilotChat never unmounts + remounts the input (which would lose focus).
  const CustomInput = useMemo(
    () =>
      function CustomInputComponent(props: InputProps) {
        return (
          <SlashCommandInput
            {...props}
            onNewConversation={() => callbacksRef.current.onNewConversation()}
            onClearMessages={() => callbacksRef.current.reset()}
            editEventRef={editEventRef}
          />
        );
      },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const CustomUserMessage = useMemo(
    () =>
      function CustomUserMessageComponent(props: UserMessageProps) {
        return (
          <EditableUserMessage
            {...props}
            onEdit={(text) => editEventRef.current?.(text)}
          />
        );
      },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  );

  // CustomAssistantMessage — routes content through A2UIMessageRenderer.
  // Structured JSON responses render as CalendarCard / EmailSummaryCard /
  // ProjectStatusWidget; plain text falls back to ReactMarkdown.
  const CustomAssistantMessage = useMemo(
    () =>
      function CustomAssistantMessageComponent({
        message,
      }: AssistantMessageProps) {
        const content =
          message && typeof message.content === "string"
            ? message.content
            : "";
        return (
          <div className="px-3 pb-2">
            <A2UIMessageRenderer content={content} role="assistant" />
          </div>
        );
      },
    []
  );

  const exportAsMarkdown = () => {
    const lines: string[] = [
      "# Blitz Conversation Export",
      "",
      `*Exported: ${new Date().toLocaleString()}*`,
      "",
    ];
    (messages as ChatMessage[]).forEach((msg) => {
      if (msg.role === "user") {
        const content =
          typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content);
        lines.push(`**You:** ${content}`, "");
      } else if (msg.role === "assistant") {
        const content =
          typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content);
        lines.push(`**Blitz:** ${content}`, "");
      }
    });
    const markdown = lines.join("\n");
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `blitz-conversation-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full text-gray-900 relative">
      {/* Header bar — shown on all screen sizes */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-white text-gray-900">
        <div className="flex items-center gap-3 md:hidden">
          <button
            onClick={onSidebarToggle}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-600"
            aria-label="Open sidebar"
          >
            &#9776;
          </button>
          <span className="text-sm font-medium text-gray-700">Blitz</span>
        </div>
        <div className="hidden md:block text-sm font-medium text-gray-700">Blitz</div>
        <button
          onClick={exportAsMarkdown}
          className="text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded px-2 py-1 hover:bg-gray-50 transition-colors"
          title="Export conversation as markdown"
          aria-label="Export conversation as markdown"
        >
          &#8595; Export
        </button>
      </div>

      <CopilotChat
        className="flex-1 min-h-0"
        instructions={SYSTEM_PROMPT}
        labels={{
          title: "Blitz",
          initial: BLITZ_WELCOME_MESSAGE,
          placeholder:
            "Ask anything... (Enter to send, Shift+Enter for new line)",
        }}
        Input={CustomInput}
        UserMessage={CustomUserMessage}
        AssistantMessage={CustomAssistantMessage}
        onInProgress={handleInProgress}
      />
      {isProcessing && (
        <div className="absolute bottom-[60px] left-0 right-0 pointer-events-none">
          <TypingIndicator />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatPanel — outer wrapper with CopilotKit provider
// ---------------------------------------------------------------------------
export function ChatPanel({
  conversationId,
  onSidebarToggle,
  onNewConversation,
  onConversationUpdate,
}: ChatPanelProps) {
  if (!conversationId) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <div className="text-center">
          <p className="text-lg mb-2">No conversation selected</p>
          <p className="text-sm">Start a new conversation from the sidebar</p>
        </div>
      </div>
    );
  }

  return (
    // key forces full remount when conversation changes — clears CopilotKit
    // message state and triggers history restore via useEffect in ChatPanelInner.
    <CopilotKit
      key={conversationId}
      runtimeUrl="/api/copilotkit"
      agent="blitz_master"
      threadId={conversationId}
    >
      <ChatPanelInner
        conversationId={conversationId}
        onSidebarToggle={onSidebarToggle}
        onNewConversation={onNewConversation}
        onConversationUpdate={onConversationUpdate}
      />
    </CopilotKit>
  );
}
