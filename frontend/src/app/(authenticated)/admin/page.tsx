/**
 * Admin Registry hub — shows entity type counts with navigation links.
 *
 * Server Component: fetches counts server-side; if any fetch fails, shows 0.
 */
import Link from "next/link";
import { auth } from "@/auth";

const BACKEND_URL =
  process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface EntityType {
  label: string;
  type: string;
  href: string;
}

const ENTITY_TYPES: EntityType[] = [
  { label: "Agents", type: "agent", href: "/admin/agents" },
  { label: "Skills", type: "skill", href: "/admin/skills" },
  { label: "Tools", type: "tool", href: "/admin/tools" },
  { label: "MCP Servers", type: "mcp_server", href: "/admin/mcp-servers" },
];

async function fetchCount(type: string, accessToken: string): Promise<number> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/registry?type=${type}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (!res.ok) return 0;
    const data = (await res.json()) as unknown[];
    return Array.isArray(data) ? data.length : 0;
  } catch {
    return 0;
  }
}

export default async function AdminRegistryPage() {
  const session = await auth();
  const accessToken =
    ((session as unknown as Record<string, unknown>).accessToken as string | undefined) ?? "";

  const counts = await Promise.all(
    ENTITY_TYPES.map((e) => fetchCount(e.type, accessToken))
  );

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Registry</h2>
        <p className="text-sm text-gray-500 mt-1">
          Navigate to any entity type to manage its definitions.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {ENTITY_TYPES.map(({ label, href }, idx) => (
          <Link
            key={href}
            href={href}
            className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-400 hover:shadow-sm transition-all"
          >
            <h2 className="text-3xl font-bold text-gray-900">{counts[idx]}</h2>
            <p className="text-base text-gray-600 mt-1">{label}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
