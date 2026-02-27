"use client";

interface RunControlsProps {
  isRunning: boolean;
  onRun: () => void;
}

export function RunControls({ isRunning, onRun }: RunControlsProps) {
  return (
    <button
      onClick={onRun}
      disabled={isRunning}
      className={`
        px-4 py-1.5 rounded text-sm font-medium transition-colors
        ${
          isRunning
            ? "bg-gray-200 text-gray-400 cursor-not-allowed"
            : "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800"
        }
      `}
    >
      {isRunning ? (
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
          Running...
        </span>
      ) : (
        "Run"
      )}
    </button>
  );
}
