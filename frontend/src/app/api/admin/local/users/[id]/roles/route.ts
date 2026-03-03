/**
 * Next.js proxy for POST /api/admin/local/users/{id}/roles.
 * Adds direct role assignments to a user.
 */

import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/server-auth";

const API = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    const res = await fetch(`${API}/api/admin/local/users/${id}/roles`, {
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
      { error: "Failed to add roles" },
      { status: 500 }
    );
  }
}
