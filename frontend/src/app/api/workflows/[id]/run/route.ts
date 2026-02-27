// frontend/src/app/api/workflows/[id]/run/route.ts
/**
 * Server-side proxy for POST /api/workflows/{id}/run.
 * Injects the server-side Bearer token — credentials never touch the browser.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(
  _: NextRequest,
  { params }: { params: Promise<{ id: string }> }
): Promise<NextResponse> {
  const { id } = await params;
  const session = await auth();
  const accessToken = (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;
  if (!accessToken)
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const res = await fetch(`${BACKEND}/api/workflows/${id}/run`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Failed to run workflow" }, { status: 500 });
  }
}
