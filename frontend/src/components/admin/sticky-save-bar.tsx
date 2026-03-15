"use client";
/**
 * StickySaveBar — fixed bottom bar that appears when there are unsaved changes.
 *
 * Shows "Unsaved changes" text, Discard button (outline), and Save button
 * (primary blue with spinner when saving).
 */

interface StickySaveBarProps {
  hasChanges: boolean;
  saving: boolean;
  onSave: () => void;
  onDiscard: () => void;
}

export function StickySaveBar({
  hasChanges,
  saving,
  onSave,
  onDiscard,
}: StickySaveBarProps) {
  if (!hasChanges) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 shadow-lg transition-transform duration-200">
      <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">
          Unsaved changes
        </span>
        <div className="flex items-center gap-3">
          <button
            onClick={onDiscard}
            disabled={saving}
            className="px-4 py-1.5 text-sm font-medium border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Discard
          </button>
          <button
            onClick={onSave}
            disabled={saving}
            className="px-4 py-1.5 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {saving && (
              <svg
                className="animate-spin h-4 w-4 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            )}
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
