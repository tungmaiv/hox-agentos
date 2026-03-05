/**
 * Workflow editor page — Server Component shell.
 *
 * Fetches the workflow by ID from the backend and renders the canvas editor
 * (Client Component). Redirects to /workflows if the workflow is not found
 * or not accessible.
 *
 * Route: /workflows/[id]
 */
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { CanvasEditor } from "./canvas-editor";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface WorkflowEditorPageProps {
  params: Promise<{ id: string }>;
}

export default async function WorkflowEditorPage({
  params,
}: WorkflowEditorPageProps) {
  const { id } = await params;
  // Middleware guarantees only authenticated users reach this page.
  const session = await auth();

  const accessToken = (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;

  // If session exists but token is missing, redirect to workflows list gracefully
  if (!accessToken) redirect("/workflows");

  const res = await fetch(`${BACKEND}/api/workflows/${id}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });

  if (!res.ok) redirect("/workflows");

  const workflow = (await res.json()) as {
    id: string;
    name: string;
    description: string | null;
    definition_json: {
      schema_version: "1.0";
      nodes: unknown[];
      edges: unknown[];
    };
  };

  return <CanvasEditor workflow={workflow} />;
}
