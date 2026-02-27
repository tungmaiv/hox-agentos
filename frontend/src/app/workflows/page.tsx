/**
 * Workflow list page — Server Component.
 *
 * Fetches the user's workflows and available templates from the backend,
 * renders a list with links to the canvas editor.
 *
 * Route: /workflows
 */
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import Link from "next/link";
import { PendingBadge } from "./_pending-badge";
import { TemplateCard } from "@/components/canvas/TemplateCard";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface WorkflowListItem {
  id: string;
  name: string;
  description: string | null;
  updated_at: string;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string | null;
}

async function fetchJson<T>(url: string, token: string): Promise<T> {
  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [] as unknown as T;
    return (await res.json()) as T;
  } catch {
    return [] as unknown as T;
  }
}

export default async function WorkflowsPage() {
  const session = await auth();
  if (!session) redirect("/login");

  const accessToken = (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;
  if (!accessToken) redirect("/login");

  const [workflows, templates] = await Promise.all([
    fetchJson<WorkflowListItem[]>(`${BACKEND}/api/workflows`, accessToken),
    fetchJson<WorkflowTemplate[]>(
      `${BACKEND}/api/workflows/templates`,
      accessToken
    ),
  ]);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
          <PendingBadge />
        </div>
        <Link
          href="/workflows/new"
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium transition-colors"
        >
          + New Workflow
        </Link>
      </div>

      {/* Template gallery */}
      {templates.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-3 text-gray-700">
            Start from a template
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                template={{
                  id: t.id,
                  name: t.name,
                  description: t.description,
                }}
              />
            ))}
          </div>
        </section>
      )}

      {/* User's workflows */}
      <section>
        <h2 className="text-lg font-semibold mb-3 text-gray-700">
          Your workflows
        </h2>
        {workflows.length === 0 ? (
          <p className="text-gray-400 text-sm">
            No workflows yet. Start from a template or create a new one.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {workflows.map((w) => (
              <Link
                key={w.id}
                href={`/workflows/${w.id}`}
                className="block border rounded-lg p-4 hover:border-blue-400 transition-colors"
              >
                <h3 className="font-medium text-gray-900">{w.name}</h3>
                {w.description && (
                  <p className="text-sm text-gray-500 mt-1">{w.description}</p>
                )}
                <p className="text-xs text-gray-400 mt-2">
                  Updated {new Date(w.updated_at).toLocaleDateString()}
                </p>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
