/**
 * Next.js API proxy for POST /api/admin/memory/reindex.
 *
 * Reads the JWT from the server-side session and forwards the request to the
 * backend with an Authorization header. The Client Component page calls this
 * proxy at /api/admin/memory/reindex instead of hitting the backend directly,
 * so the access token is never exposed to the browser.
 *
 * Mirrors the auth pattern used by app/api/copilotkit/route.ts.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const session = await auth();

  if (!session) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;

  if (!accessToken) {
    return NextResponse.json(
      { error: "No access token in session" },
      { status: 401 }
    );
  }

  const body = await request.text();

  const backendRes = await fetch(
    `${BACKEND_URL}/api/admin/memory/reindex`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          request.headers.get("Content-Type") ?? "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body,
    }
  );

  const data: unknown = await backendRes.json();
  return NextResponse.json(data, { status: backendRes.status });
}
