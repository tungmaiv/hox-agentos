/**
 * Next.js proxy for admin Keycloak configuration API.
 *
 * Forwards GET, POST requests to /api/admin/keycloak/* on the backend,
 * injecting the Authorization header from the server-side session.
 *
 * Routes:
 *   GET  /api/admin/keycloak/config          → GET  /api/admin/keycloak/config
 *   POST /api/admin/keycloak/config          → POST /api/admin/keycloak/config
 *   POST /api/admin/keycloak/test-connection → POST /api/admin/keycloak/test-connection
 *   POST /api/admin/keycloak/disable         → POST /api/admin/keycloak/disable
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

async function proxyToBackend(
  request: NextRequest,
  path: string[]
): Promise<NextResponse> {
  const session = await auth();

  if (!session) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;

  if (!accessToken) {
    return NextResponse.json(
      { error: "No access token in session" },
      { status: 401 }
    );
  }

  const backendPath = `/api/admin/keycloak/${path.join("/")}`;
  const body = request.method !== "GET" ? await request.text() : undefined;

  const backendRes = await fetch(`${BACKEND_URL}${backendPath}`, {
    method: request.method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body,
  });

  const responseData = (await backendRes.json()) as unknown;
  return NextResponse.json(responseData, { status: backendRes.status });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await params;
  return proxyToBackend(request, path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await params;
  return proxyToBackend(request, path);
}
