// frontend/src/app/api/admin/mcp-servers/[id]/route.ts
/**
 * Server-side proxy for GET/DELETE/PATCH /api/admin/mcp-servers/{id}.
 * Injects the server-side Bearer token — credentials never touch the browser.
 *
 * GET    — proxies to backend (handles both check-name and /{id}/health sub-paths)
 * DELETE — removes a registered MCP server
 * PATCH  — updates MCP server status
 *
 * Non-admin users receive the backend 403 response forwarded as-is.
 * 404 is forwarded when the server_id does not exist.
 */

import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/server-auth";

const API_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function proxyToBackend(
  request: NextRequest,
  id: string,
  method: string,
  body?: string
): Promise<NextResponse> {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const backendUrl = new URL(`/api/admin/mcp-servers/${id}`, API_URL);
  request.nextUrl.searchParams.forEach((value, key) => {
    backendUrl.searchParams.append(key, value);
  });

  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };
  if (body) headers["Content-Type"] = "application/json";

  try {
    const response = await fetch(backendUrl.toString(), {
      method,
      headers,
      ...(body ? { body } : {}),
      cache: "no-store",
    });
    const data = (await response.json()) as unknown;
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to proxy MCP server request" },
      { status: 500 }
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
): Promise<NextResponse> {
  const { id } = await params;
  return proxyToBackend(request, id, "GET");
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
): Promise<NextResponse> {
  const { id } = await params;
  const body = await request.text();
  return proxyToBackend(request, id, "PATCH", body || undefined);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
): Promise<NextResponse> {
  const { id } = await params;
  return proxyToBackend(request, id, "DELETE");
}
