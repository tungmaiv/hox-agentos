/**
 * New Workflow page — Server Component.
 *
 * Creates a new empty workflow via POST /api/workflows, then redirects to
 * the canvas editor at /workflows/{id}.
 *
 * This static segment (/workflows/new) takes priority over the dynamic
 * segment (/workflows/[id]) when navigating to /workflows/new.
 *
 * Route: /workflows/new
 */
import { auth } from "@/auth";
import { redirect } from "next/navigation";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default async function NewWorkflowPage() {
  const session = await auth();
  if (!session) redirect("/login");

  const accessToken = (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;
  if (!accessToken) redirect("/login");

  const res = await fetch(`${BACKEND}/api/workflows`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name: "Untitled Workflow",
      definition_json: { schema_version: "1.0", nodes: [], edges: [] },
    }),
    cache: "no-store",
  });

  if (!res.ok) redirect("/workflows");

  const workflow = (await res.json()) as { id: string };
  redirect(`/workflows/${workflow.id}`);
}
