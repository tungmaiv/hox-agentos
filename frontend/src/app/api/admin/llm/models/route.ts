/**
 * Next.js API proxy for GET/POST /api/admin/llm/models.
 *
 * Forwards requests to the backend with Authorization header from server-side session.
 * The LLM config Client Component calls this proxy instead of hitting the backend directly.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAccessToken(): Promise<string | null> {
  const session = await auth();
  if (!session) return null;
  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  return accessToken ?? null;
}

export async function GET(_request: NextRequest): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const backendRes = await fetch(`${BACKEND_URL}/api/admin/llm/models`, {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });

  const data: unknown = await backendRes.json();
  return NextResponse.json(data, { status: backendRes.status });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const body = await request.text();

  const backendRes = await fetch(`${BACKEND_URL}/api/admin/llm/models`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body,
  });

  const data: unknown = await backendRes.json();
  return NextResponse.json(data, { status: backendRes.status });
}
