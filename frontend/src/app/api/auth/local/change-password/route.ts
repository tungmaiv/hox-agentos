/**
 * Server-side proxy for POST /api/auth/local/change-password.
 * Injects the server-side Bearer token — credentials never touch the browser.
 */
import { getAccessToken } from "@/lib/server-auth";
import { NextRequest, NextResponse } from "next/server";

const API_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body: unknown = await request.json();
    const res = await fetch(`${API_URL}/api/auth/local/change-password`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });
    const data: unknown = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to change password" },
      { status: 500 }
    );
  }
}
