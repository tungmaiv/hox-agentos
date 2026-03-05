"use client";
/**
 * LLMPreferencesCard — controls for LLM interaction preferences.
 *
 * Thinking mode: toggle switch (auto-saves on change).
 * Response style: radio group — concise / detailed / conversational (auto-saves on change).
 *
 * Auto-save: PUT /api/users/me/preferences on every toggle/radio change.
 * Feedback: brief inline "Saved ✓" that fades after 1.5 seconds (no toast).
 *
 * Backend API (Plan 16-01): GET/PUT /api/users/me/preferences
 * Proxy route: /api/users/me/preferences (Plan 16-03, created alongside this card)
 */
import { useEffect, useRef, useState } from "react";

interface Preferences {
  thinking_mode: boolean;
  response_style: "concise" | "detailed" | "conversational";
}

const RESPONSE_STYLE_OPTIONS: {
  value: Preferences["response_style"];
  label: string;
  description: string;
}[] = [
  {
    value: "concise",
    label: "Concise",
    description: "Short, direct answers",
  },
  {
    value: "detailed",
    label: "Detailed",
    description: "Thorough explanations with examples",
  },
  {
    value: "conversational",
    label: "Conversational",
    description: "Friendly, engaging, ask follow-ups",
  },
];

export function LLMPreferencesCard() {
  const [prefs, setPrefs] = useState<Preferences>({
    thinking_mode: false,
    response_style: "concise",
  });
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  useEffect(() => {
    fetch("/api/users/me/preferences", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: Preferences) => {
        setPrefs(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  function showIndicator(ok: boolean) {
    setSaved(ok);
    setSaveError(!ok);
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      setSaved(false);
      setSaveError(false);
    }, 1500);
  }

  async function updatePrefs(partial: Partial<Preferences>) {
    const previous = prefs;
    const updated = { ...prefs, ...partial };
    setPrefs(updated);

    try {
      const res = await fetch("/api/users/me/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(partial),
      });
      if (res.ok) {
        showIndicator(true);
      } else {
        setPrefs(previous);
        showIndicator(false);
      }
    } catch {
      setPrefs(previous);
      showIndicator(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-gray-900">
          AI Preferences
        </h2>
        {saved && (
          <span className="text-xs text-green-600 font-medium flex items-center gap-1">
            <svg
              className="w-3 h-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M5 13l4 4L19 7"
              />
            </svg>
            Saved
          </span>
        )}
        {saveError && (
          <span className="text-xs text-red-600 font-medium flex items-center gap-1">
            <svg
              className="w-3 h-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
            Not saved
          </span>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Loading preferences...</p>
      ) : (
        <div className="space-y-6">
          {/* Thinking mode toggle */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">Thinking mode</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Blitz shows its reasoning process before answering
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={prefs.thinking_mode}
              onClick={() =>
                void updatePrefs({ thinking_mode: !prefs.thinking_mode })
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                prefs.thinking_mode ? "bg-blue-600" : "bg-gray-200"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform ${
                  prefs.thinking_mode ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Response style radio group */}
          <div>
            <p className="text-sm font-medium text-gray-900 mb-3">
              Response style
            </p>
            <div className="space-y-2">
              {RESPONSE_STYLE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className="flex items-center gap-3 cursor-pointer group"
                >
                  <input
                    type="radio"
                    name="response-style"
                    value={option.value}
                    checked={prefs.response_style === option.value}
                    onChange={() =>
                      void updatePrefs({ response_style: option.value })
                    }
                    className="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-900 group-hover:text-blue-700 transition-colors">
                      {option.label}
                    </span>
                    <span className="text-xs text-gray-500 ml-2">
                      — {option.description}
                    </span>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
