// frontend/src/app/settings/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";

interface UserInstructionsResponse {
  instructions: string;
  updated_at: string;
}

export default function SettingsPage() {
  const { data: session } = useSession();
  const [instructions, setInstructions] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const accessToken = (session as unknown as Record<string, unknown>)
      ?.accessToken as string | undefined;
    if (!accessToken) return;

    fetch("/api/user/instructions/", {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => r.json())
      .then((data: UserInstructionsResponse) => {
        setInstructions(data.instructions ?? "");
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [session]);

  async function handleSave() {
    const accessToken = (session as unknown as Record<string, unknown>)
      ?.accessToken as string | undefined;
    if (!accessToken) return;

    await fetch("/api/user/instructions/", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ instructions }),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (loading) {
    return (
      <div className="p-8 text-gray-500">Loading...</div>
    );
  }

  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="mb-6">
        <Link
          href="/chat"
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; Back to chat
        </Link>
      </div>

      <h1 className="text-2xl font-semibold mb-6">Settings</h1>

      <section className="mb-8">
        <h2 className="text-lg font-medium mb-1">Custom Instructions</h2>
        <p className="text-sm text-gray-500 mb-4">
          These instructions are appended to every conversation with Blitz.
          Example: &quot;Always respond in Vietnamese&quot; or &quot;I am a backend engineer.&quot;
        </p>
        <textarea
          className="w-full min-h-[160px] p-3 border border-gray-300 rounded-md font-mono text-sm resize-y focus:outline-none focus:ring-2 focus:ring-blue-500"
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
