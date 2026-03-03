// frontend/src/app/api/admin/credentials/[userId]/[provider]/route.ts
/**
 * Server-side proxy for DELETE /api/admin/credentials/{user_id}/{provider}.
 * Injects the server-side Bearer token — credentials never touch the browser.
 *
 * Forwards admin force-revoke to backend. Returns 204 on success.
 * Non-admin users receive the backend 403 response forwarded as-is.
 */

import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/server-auth";

const API_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ userId: string; provider: string }> }
): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { userId, provider } = await params;

  try {
    const response = await fetch(
      `${API_URL}/api/admin/credentials/${encodeURIComponent(userId)}/${encodeURIComponent(provider)}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${accessToken}` },
      }
    );

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }
    const data = (await response.json().catch(() => ({}))) as unknown;
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to revoke credential" },
      { status: 500 }
    );
  }
}
