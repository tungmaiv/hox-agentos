// frontend/src/app/settings/page.tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface UserInstructionsResponse {
  instructions: string;
  updated_at: string;
}

export default function SettingsPage() {
  const [instructions, setInstructions] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/user/instructions/", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: UserInstructionsResponse) => {
        setInstructions(data.instructions ?? "");
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  async function handleSave() {
    const res = await fetch("/api/user/instructions/", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instructions }),
    });
    if (res.ok) {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  }

  if (loading) {
    return <div className="p-8 text-gray-500">Loading...</div>;
  }

  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="mb-6">
        <Link href="/chat" className="text-sm text-blue-600 hover:underline">
          &larr; Back to chat
        </Link>
      </div>

      <h1 className="text-2xl font-semibold mb-6">Settings</h1>

      <nav className="mb-8">
        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
          Personal
        </h2>
        <div className="grid grid-cols-2 gap-3 mb-6">
          <Link
            href="/settings/memory"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">Memory</p>
              <p className="text-xs text-gray-500 mt-0.5">
                View and delete stored facts
              </p>
            </div>
          </Link>
          <Link
            href="/settings/chat-preferences"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">
                Chat Preferences
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                Rendering mode selection
              </p>
            </div>
          </Link>
          <Link
            href="/settings/channels"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">
                Channel Linking
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                Connect Telegram, WhatsApp, Teams
              </p>
            </div>
          </Link>
        </div>

        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
          Admin
        </h2>
        <div className="grid grid-cols-2 gap-3">
          <Link
            href="/settings/agents"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">Agents</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Enable or disable AI agents
              </p>
            </div>
          </Link>
          <Link
            href="/settings/integrations"
            className="flex items-center p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
          >
            <div>
              <p className="text-sm font-medium text-gray-900">Integrations</p>
              <p className="text-xs text-gray-500 mt-0.5">
                MCP server connections
              </p>
            </div>
          </Link>
        </div>
      </nav>

      <section className="mb-8">
        <h2 className="text-lg font-medium mb-1">Custom Instructions</h2>
        <p className="text-sm text-gray-500 mb-4">
          These instructions are appended to every conversation with Blitz.
          Example: &quot;Always respond in Vietnamese&quot; or &quot;I am a
          backend engineer.&quot;
        </p>
        <textarea
          className="w-full min-h-[160px] p-3 border border-gray-300 rounded-md font-mono text-sm text-gray-900 bg-white resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          placeholder="Add custom instructions that Blitz will follow in every conversation..."
          maxLength={4000}
        />
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-gray-400">
            {instructions.length}/4000 characters
          </span>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors"
          >
            {saved ? "Saved \u2713" : "Save Instructions"}
          </button>
        </div>
      </section>
    </main>
  );
}
