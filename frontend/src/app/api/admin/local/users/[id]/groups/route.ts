/**
 * Next.js proxy for POST /api/admin/local/users/{id}/groups.
 * Assigns one or more groups to a user.
 */

import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAccessToken(): Promise<string | null> {
  const session = await auth();
  if (!session) return null;
  return (session as unknown as Record<string, unknown>)
    .accessToken as string | null;
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
): Promise<NextResponse> {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  try {
    const body = (await req.json()) as unknown;
    const res = await fetch(`${API}/api/admin/local/users/${id}/groups`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (res.status === 204) {
      return new NextResponse(null, { status: 204 });
    }
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to assign groups" },
      { status: 500 }
    );
  }
}
