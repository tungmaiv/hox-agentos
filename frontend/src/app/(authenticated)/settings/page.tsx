"use client";
/**
 * Settings page — application configuration.
 *
 * Plan 16-03: Removed custom instructions textarea (moved to /profile)
 * and Chat Preferences card link (LLM prefs now on /profile).
 * Removed "Back to chat" link (nav rail handles navigation now).
 *
 * Remaining items: Memory, Channel Linking.
 */
import Link from "next/link";

export default function SettingsPage() {
  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Application configuration</p>
      </div>

      <nav>
        <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
          Personal
        </h2>
        <div className="grid grid-cols-2 gap-3">
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
      </nav>
    </main>
  );
}
