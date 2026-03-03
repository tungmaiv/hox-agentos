// frontend/src/app/api/admin/config/[key]/route.ts
/**
 * Server-side proxy for PUT /api/admin/config/{key}.
 * Injects the server-side Bearer token — credentials never touch the browser.
 *
 * Forwards the JSON body to the backend and returns the updated {key, value}.
 * Non-admin users receive the backend 403 response forwarded as-is.
 */

import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/server-auth";

const API_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> }
): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { key } = await params;

  try {
    const body = (await request.json()) as unknown;
    const response = await fetch(`${API_URL}/api/admin/config/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });
    const data = (await response.json()) as unknown;
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to update config" },
      { status: 500 }
    );
  }
}
