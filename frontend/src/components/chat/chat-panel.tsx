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
 */
import { useState, useRef, useEffect } from "react";
import { CopilotKit, useCopilotChatInternal } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import type { InputProps, UserMessageProps } from "@copilotkit/react-ui";

/** Minimal Message shape for export serialization (role + content fields from AG-UI). */
interface ChatMessage {
  role: string;
  content?: string | unknown;
}

interface ChatPanelProps {
  conversationId: string | null;
  onSidebarToggle: () => void;
  onNewConversation: () => void;
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

Format your responses with markdown when it improves clarity (headers, bold, code blocks). Keep responses focused and appropriately concise.`;

// ---------------------------------------------------------------------------
// Custom Input component — intercepts slash commands before sending
// ---------------------------------------------------------------------------
interface SlashInputProps extends InputProps {
  onNewConversation: () => void;
  onClearMessages: () => void;
  pendingInputRef: React.MutableRefObject<string>;
  setPendingInput: (v: string) => void;
}

function SlashCommandInput({
  onSend,
  inProgress,
  onStop,
  onNewConversation,
  onClearMessages,
  pendingInputRef,
  setPendingInput,
}: SlashInputProps) {
  const [inputValue, setInputValue] = useState(pendingInputRef.current ?? "");

  // Sync back when parent sets pendingInput (e.g. from edit message)
  useEffect(() => {
    if (pendingInputRef.current && pendingInputRef.current !== inputValue) {
      setInputValue(pendingInputRef.current);
    }
  }, [pendingInputRef.current]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSlashCommand = (value: string): boolean => {
    const trimmed = value.trim();
    if (trimmed === "/new") {
      onNewConversation();
      return true; // consumed — do not send to agent
    }
    if (trimmed === "/clear") {
      onClearMessages();
      return true; // consumed — do not send to agent
    }
    return false;
  };

  const handleKeyDown = async (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!inputValue.trim() || inProgress) return;
      if (handleSlashCommand(inputValue)) {
        setInputValue("");
        setPendingInput("");
        return;
      }
      const text = inputValue;
      setInputValue("");
      setPendingInput("");
      await onSend(text);
    }
  };

  return (
    <div className="flex items-end gap-2 p-3 border-t border-gray-200 bg-white">
      <textarea
        className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[44px] max-h-40"
        placeholder="Ask anything... (Enter to send, Shift+Enter for new line, /new for new chat, /clear to clear)"
        value={inputValue}
        onChange={(e) => {
          setInputValue(e.target.value);
          setPendingInput(e.target.value);
        }}
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
                setPendingInput("");
                return;
              }
              const text = inputValue;
              setInputValue("");
              setPendingInput("");
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
// Inner panel — must be inside CopilotKit context to use hooks
// ---------------------------------------------------------------------------
interface ChatPanelInnerProps {
  onSidebarToggle: () => void;
  onNewConversation: () => void;
}

function ChatPanelInner({ onSidebarToggle, onNewConversation }: ChatPanelInnerProps) {
  const { messages, reset, stopGeneration, isLoading } = useCopilotChatInternal();

  // Shared state for edit message: fills the input
  const pendingInputRef = useRef("");
  const [pendingInput, setPendingInputState] = useState("");

  const setPendingInput = (v: string) => {
    pendingInputRef.current = v;
    setPendingInputState(v);
  };

  const handleClearMessages = () => {
    reset();
  };

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

  const handleEditMessage = (text: string) => {
    setPendingInput(text);
  };

  // Build custom Input and UserMessage components with closures
  const CustomInput = (props: InputProps) => (
    <SlashCommandInput
      {...props}
      onNewConversation={onNewConversation}
      onClearMessages={handleClearMessages}
      pendingInputRef={pendingInputRef}
      setPendingInput={setPendingInput}
    />
  );

  const CustomUserMessage = (props: UserMessageProps) => (
    <EditableUserMessage {...props} onEdit={handleEditMessage} />
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header bar — shown on all screen sizes */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-white">
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
        className="flex-1"
        instructions={SYSTEM_PROMPT}
        labels={{
          title: "Blitz",
          initial: BLITZ_WELCOME_MESSAGE,
          placeholder:
            "Ask anything... (Enter to send, Shift+Enter for new line)",
        }}
        Input={CustomInput}
        UserMessage={CustomUserMessage}
        onInProgress={(inProgress) => {
          // Track generation state changes if needed
          void inProgress;
        }}
      />
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
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      agent="blitz_master"
      threadId={conversationId}
    >
      <ChatPanelInner
        onSidebarToggle={onSidebarToggle}
        onNewConversation={onNewConversation}
      />
    </CopilotKit>
  );
}
