// frontend/src/components/chat/conversation-sidebar.tsx
"use client";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import type { Conversation } from "./chat-layout";

interface ConversationSidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  userEmail: string;
  onNewConversation: () => void;
  onSelectConversation: (id: string) => void;
  onConversationsChange: (conversations: Conversation[]) => void;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  userEmail,
  onNewConversation,
  onSelectConversation,
  onConversationsChange,
}: ConversationSidebarProps) {
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const handleDelete = (conversationId: string) => {
    // Optimistic update — remove from UI immediately
    onConversationsChange(
      conversations.filter((c) => c.conversation_id !== conversationId)
    );
    setMenuOpenId(null);
    // Persist deletion via proxy route (fire-and-forget — optimistic update already applied)
    fetch(`/api/conversations/${conversationId}`, {
      method: "DELETE",
    }).catch(() => {
      // Non-critical on failure — sidebar will revert on next refresh
    });
  };

  const handleRename = (conv: Conversation) => {
    setRenamingId(conv.conversation_id);
    setRenameValue(conv.title);
    setMenuOpenId(null);
  };

  const handleRenameSubmit = (conversationId: string) => {
    const trimmed = renameValue.trim();
    if (!trimmed) {
      setRenamingId(null);
      return;
    }
    // Optimistic update
    onConversationsChange(
      conversations.map((c) =>
        c.conversation_id === conversationId ? { ...c, title: trimmed } : c
      )
    );
    setRenamingId(null);
    // Persist to DB via proxy route (fire-and-forget — optimistic update already applied)
    fetch(`/api/conversations/${conversationId}/title`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: trimmed }),
    }).catch(() => {
      // Non-critical on failure — sidebar will revert on next refresh
    });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-lg font-semibold text-gray-900">Blitz</h1>
          <span className="text-xs text-gray-400 truncate max-w-[120px]">
            {userEmail}
          </span>
        </div>
        <button
          onClick={onNewConversation}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors"
        >
          <span>+ New Conversation</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {conversations.length === 0 && (
          <p className="text-center text-sm text-gray-400 mt-8 px-4">
            No conversations yet. Start a new one above.
          </p>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.conversation_id}
            className={`group relative flex items-center gap-2 px-3 py-2 mx-2 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors ${
              activeConversationId === conv.conversation_id ? "bg-gray-100" : ""
            }`}
            onClick={() => onSelectConversation(conv.conversation_id)}
          >
            {renamingId === conv.conversation_id ? (
              <input
                autoFocus
                className="flex-1 text-sm text-gray-900 bg-white border border-blue-400 rounded px-2 py-1 outline-none"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onBlur={() => handleRenameSubmit(conv.conversation_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRenameSubmit(conv.conversation_id);
                  if (e.key === "Escape") setRenamingId(null);
                }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 truncate">{conv.title}</p>
                  <p className="text-xs text-gray-400">
                    {formatDistanceToNow(new Date(conv.last_message_at), {
                      addSuffix: true,
                    })}
                  </p>
                </div>
                <button
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-gray-200 text-gray-500 transition-opacity"
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuOpenId(
                      menuOpenId === conv.conversation_id
                        ? null
                        : conv.conversation_id
                    );
                  }}
                  aria-label="Conversation options"
                >
                  &#8942;
                </button>
                {menuOpenId === conv.conversation_id && (
                  <div className="absolute right-2 top-8 z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[120px]">
                    <button
                      className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRename(conv);
                      }}
                    >
                      Rename
                    </button>
                    <button
                      className="w-full text-left px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(conv.conversation_id);
                      }}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>

    </div>
  );
}
