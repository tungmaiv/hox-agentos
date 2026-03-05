// frontend/src/app/api/workflows/route.ts
/**
 * Server-side proxy for GET/POST /api/workflows.
 * Injects the server-side Bearer token — credentials never touch the browser.
 */
import { getAccessToken } from "@/lib/server-auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken)
    return NextResponse.json([], { status: 401 });

  try {
    const res = await fetch(`${BACKEND}/api/workflows`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Failed to fetch workflows" }, { status: 500 });
  }
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken)
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const body = (await req.json()) as unknown;
    const res = await fetch(`${BACKEND}/api/workflows`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Failed to create workflow" }, { status: 500 });
  }
}
