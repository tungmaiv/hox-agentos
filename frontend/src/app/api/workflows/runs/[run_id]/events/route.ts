// frontend/src/app/api/workflows/runs/[run_id]/events/route.ts
/**
 * Server-side proxy for GET /api/workflows/runs/{run_id}/events (SSE stream).
 * Passes through the SSE stream from the backend to the client.
 */
import { auth } from "@/auth";
import { NextRequest } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(
  _: NextRequest,
  { params }: { params: Promise<{ run_id: string }> }
): Promise<Response> {
  const { run_id } = await params;
  const session = await auth();
  const accessToken = (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;
  if (!accessToken) return new Response("Unauthorized", { status: 401 });

  try {
    const backendRes = await fetch(
      `${BACKEND}/api/workflows/runs/${run_id}/events`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          Accept: "text/event-stream",
        },
      }
    );
    return new Response(backendRes.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch {
    return new Response("Failed to connect to event stream", { status: 500 });
  }
}
