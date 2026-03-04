// frontend/src/app/api/workflows/runs/pending-hitl/route.ts
/**
 * Server-side proxy for GET /api/workflows/runs/pending-hitl.
 * Returns the count of workflow runs paused waiting for human approval.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(): Promise<NextResponse> {
  const session = await auth();
  const accessToken = (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;
  if (!accessToken) return NextResponse.json({ count: 0 });

  try {
    const res = await fetch(`${BACKEND}/api/workflows/runs/pending-hitl`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ count: 0 });
  }
}
