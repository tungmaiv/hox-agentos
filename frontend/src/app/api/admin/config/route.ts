// frontend/src/app/api/admin/config/route.ts
/**
 * Server-side proxy for GET /api/admin/config.
 * Injects the server-side Bearer token — credentials never touch the browser.
 *
 * Returns the full system config dict to admin users.
 * Non-admin users receive the backend 403 response forwarded as-is.
 */

import { NextResponse } from "next/server";
import { getAccessToken } from "@/lib/server-auth";

const API_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function GET(): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const response = await fetch(`${API_URL}/api/admin/config`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    const data = (await response.json()) as unknown;
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to fetch config" },
      { status: 500 }
    );
  }
}
