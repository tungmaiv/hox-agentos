/**
 * Server-side proxy for POST /api/admin/mcp-servers/test.
 * Tests MCP server connectivity with the provided URL and optional auth token.
 * Injects the server-side Bearer token for backend auth.
 */

import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/server-auth";

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
    const body = (await request.json()) as unknown;
    const response = await fetch(`${API_URL}/api/admin/mcp-servers/test`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const data = (await response.json()) as unknown;
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to test MCP server connection" },
      { status: 500 }
    );
  }
}
