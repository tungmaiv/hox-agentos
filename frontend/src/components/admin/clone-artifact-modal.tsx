"use client";
/**
 * CloneArtifactModal — searchable modal to pick an existing artifact for cloning.
 *
 * Fetches the list of artifacts of the chosen type on open, filters client-side,
 * and calls onSelect with the chosen artifact. Caller appends "_copy" to name.
 */
import { useEffect, useRef, useState } from "react";
import { z } from "zod";

const ArtifactItemSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().optional(),
});

type ArtifactItem = z.infer<typeof ArtifactItemSchema>;

const TYPE_TO_PATH: Record<string, string> = {
  agent: "agents",
  tool: "tools",
  skill: "skills",
  mcp_server: "mcp-servers",
};

interface CloneArtifactModalProps {
  /** "agent" | "tool" | "skill" | "mcp_server" */
  artifactType: string;
  onSelect: (artifact: { id: string; name: string; [key: string]: unknown }) => void;
  onClose: () => void;
}

export function CloneArtifactModal({
  artifactType,
  onSelect,
  onClose,
}: CloneArtifactModalProps) {
  const [items, setItems] = useState<ArtifactItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const typePath = TYPE_TO_PATH[artifactType];

  useEffect(() => {
    // Focus search on open
    searchRef.current?.focus();

    if (!typePath) {
      setError("Unknown artifact type");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    fetch(`/api/admin/${typePath}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const raw: unknown = await res.json();
        const parsed = z.array(ArtifactItemSchema).safeParse(raw);
        if (!parsed.success) throw new Error("Unexpected response shape");
        setItems(parsed.data);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load artifacts");
      })
      .finally(() => setLoading(false));
  }, [typePath]);

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const filtered = search
    ? items.filter(
        (item) =>
          item.name.toLowerCase().includes(search.toLowerCase()) ||
          (item.description ?? "").toLowerCase().includes(search.toLowerCase())
      )
    : items;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 flex flex-col max-h-[70vh]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">
            Clone existing {artifactType.replace("_", " ")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none"
          >
            &times;
          </button>
        </div>

        {/* Search */}
        <div className="px-5 py-3 border-b border-gray-100">
          <input
            ref={searchRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or description..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* List */}
        <div className="overflow-y-auto flex-1">
          {loading && (
            <div className="px-5 py-8 text-center text-sm text-gray-400">Loading...</div>
          )}
          {error && (
            <div className="px-5 py-4 text-center text-sm text-red-600">{error}</div>
          )}
          {!loading && !error && filtered.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-gray-400">
              {search ? "No matching artifacts" : "No artifacts found"}
            </div>
          )}
          {!loading &&
            !error &&
            filtered.map((item) => (
              <div
                key={item.id}
                className="px-5 py-3 border-b border-gray-50 last:border-0 hover:bg-gray-50 flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">{item.name}</div>
                  {item.description && (
                    <div className="text-xs text-gray-500 truncate mt-0.5">
                      {item.description}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => onSelect(item)}
                  className="flex-shrink-0 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-md hover:bg-blue-700 transition-colors"
                >
                  Use this
                </button>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
