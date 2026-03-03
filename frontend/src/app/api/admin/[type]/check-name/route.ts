/**
 * Proxy for GET /api/admin/{type}/check-name?name=...
 *
 * Validates the artifact type, then forwards to the backend check-name endpoint.
 * Returns {"available": boolean} — 400 if type or name is invalid.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const ALLOWED_TYPES = new Set(["agents", "tools", "skills", "mcp-servers"]);

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ type: string }> }
) {
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { type } = await params;
  if (!ALLOWED_TYPES.has(type)) {
    return NextResponse.json({ error: "Invalid artifact type" }, { status: 400 });
  }

  const name = req.nextUrl.searchParams.get("name");
  if (!name) {
    return NextResponse.json({ error: "name query parameter required" }, { status: 400 });
  }

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;

  try {
    const res = await fetch(
      `${BACKEND_URL}/api/admin/${type}/check-name?name=${encodeURIComponent(name)}`,
      {
        headers: {
          Authorization: `Bearer ${accessToken ?? ""}`,
        },
        cache: "no-store",
      }
    );
    const data: unknown = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }
}
