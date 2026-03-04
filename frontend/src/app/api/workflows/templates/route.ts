// frontend/src/app/api/workflows/templates/route.ts
/**
 * Server-side proxy for GET /api/workflows/templates.
 * Lists all available template workflows.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(): Promise<NextResponse> {
  const session = await auth();
  const accessToken = (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;
  if (!accessToken) return NextResponse.json([], { status: 401 });

  try {
    const res = await fetch(`${BACKEND}/api/workflows/templates`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Failed to fetch templates" }, { status: 500 });
  }
}
