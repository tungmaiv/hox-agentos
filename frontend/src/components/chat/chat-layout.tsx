// frontend/src/components/chat/chat-layout.tsx
"use client";
import { useState } from "react";
import { ConversationSidebar } from "./conversation-sidebar";
import { ChatPanel } from "./chat-panel";

export interface Conversation {
  conversation_id: string;
  title: string;
  last_message_at: string;
  message_count: number;
}

interface ChatLayoutProps {
  initialConversations: Conversation[];
  userEmail: string;
}

export function ChatLayout({ initialConversations, userEmail }: ChatLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState<Conversation[]>(initialConversations);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    initialConversations[0]?.conversation_id ?? null
  );

  const handleNewConversation = () => {
    const newId = crypto.randomUUID();
    setActiveConversationId(newId);
  };

  const handleConversationSelect = (conversationId: string) => {
    setActiveConversationId(conversationId);
    if (window.innerWidth < 768) setSidebarOpen(false);
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Mobile hamburger toggle */}
      <button
        className="fixed top-4 left-4 z-50 md:hidden bg-white border border-gray-200 rounded-md p-2 shadow-sm"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle sidebar"
      >
        <span className="block w-5 h-0.5 bg-gray-600 mb-1" />
        <span className="block w-5 h-0.5 bg-gray-600 mb-1" />
        <span className="block w-5 h-0.5 bg-gray-600" />
      </button>

      {/* Sidebar */}
      <div
        className={`
          fixed md:relative inset-y-0 left-0 z-40 w-72 bg-white border-r border-gray-200
          transform transition-transform duration-200 ease-in-out
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
          ${!sidebarOpen ? "md:w-0 md:overflow-hidden" : ""}
        `}
      >
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          userEmail={userEmail}
          onNewConversation={handleNewConversation}
          onSelectConversation={handleConversationSelect}
          onConversationsChange={setConversations}
        />
      </div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black bg-opacity-25 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Chat panel */}
      <div className="flex-1 flex flex-col min-w-0">
        <ChatPanel
          conversationId={activeConversationId}
          onSidebarToggle={() => setSidebarOpen(!sidebarOpen)}
          onNewConversation={handleNewConversation}
        />
      </div>
    </div>
  );
}
