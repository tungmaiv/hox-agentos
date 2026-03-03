"use client";
/**
 * ArtifactWizardNameCheck — debounced name availability input.
 *
 * Shows spinner while in-flight, then a checkmark (available) or X (taken)
 * badge after 300ms debounce. Reports availability to parent via callback.
 */
import { useEffect, useRef, useState } from "react";

interface Props {
  /** "agent" | "tool" | "skill" | "mcp_server" */
  artifactType: string | null;
  value: string;
  onChange: (v: string) => void;
  /** null = in-flight / not yet checked, true = available, false = taken */
  onAvailabilityChange: (available: boolean | null) => void;
  disabled?: boolean;
  onBlur?: () => void;
}

const TYPE_TO_PATH: Record<string, string> = {
  agent: "agents",
  tool: "tools",
  skill: "skills",
  mcp_server: "mcp-servers",
};

export function ArtifactWizardNameCheck({
  artifactType,
  value,
  onChange,
  onAvailabilityChange,
  disabled,
  onBlur,
}: Props) {
  const [status, setStatus] = useState<"idle" | "checking" | "available" | "taken">("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!value || !artifactType) {
      setStatus("idle");
      onAvailabilityChange(null);
      return;
    }

    setStatus("checking");
    onAvailabilityChange(null);

    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(async () => {
      const path = TYPE_TO_PATH[artifactType];
      if (!path) {
        setStatus("idle");
        return;
      }
      try {
        const res = await fetch(
          `/api/admin/${path}/check-name?name=${encodeURIComponent(value)}`
        );
        const data = (await res.json()) as { available?: boolean };
        const avail = data.available ?? false;
        setStatus(avail ? "available" : "taken");
        onAvailabilityChange(avail);
      } catch {
        setStatus("idle");
        onAvailabilityChange(null);
      }
    }, 300);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, artifactType, onAvailabilityChange]);

  const badge =
    status === "checking" ? (
      <span className="text-gray-400 text-xs ml-2 whitespace-nowrap">checking...</span>
    ) : status === "available" ? (
      <span className="text-green-600 text-xs ml-2 whitespace-nowrap">&#10003; available</span>
    ) : status === "taken" ? (
      <span className="text-red-600 text-xs ml-2 whitespace-nowrap">&#10007; taken</span>
    ) : null;

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        disabled={disabled}
        placeholder="artifact-name (lowercase, hyphens)"
        className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
      />
      {badge}
    </div>
  );
}
