/**
 * Catch-all proxy for /api/skills/* sub-paths (e.g. /{id}/export, /{name}/run).
 *
 * Forwards GET and POST requests to the backend with JWT injection.
 * Handles binary responses (ZIP) without corruption.
 *
 * Pattern: same as /api/admin/[...path]/route.ts.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

async function proxyRequest(
  request: NextRequest,
  params: Promise<{ path: string[] }>
): Promise<NextResponse> {
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  if (!accessToken) {
    return NextResponse.json({ error: "No access token" }, { status: 401 });
  }

  const { path } = await params;
  const backendPath = `/api/skills/${path.join("/")}`;
  const url = new URL(backendPath, API_URL);

  const searchParams = request.nextUrl.searchParams;
  searchParams.forEach((value, key) => url.searchParams.append(key, value));

  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };

  const fetchInit: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };

  if (["POST", "PUT", "PATCH"].includes(request.method)) {
    const contentType = request.headers.get("Content-Type");
    if (contentType) headers["Content-Type"] = contentType;
    const bodyText = await request.text();
    if (bodyText) fetchInit.body = bodyText;
  }

  try {
    const backendResponse = await fetch(url.toString(), fetchInit);
    const responseContentType =
      backendResponse.headers.get("Content-Type") ?? "application/json";

    // Binary responses — must use arrayBuffer to avoid UTF-8 corruption
    if (
      responseContentType.includes("application/zip") ||
      responseContentType.includes("application/octet-stream")
    ) {
      const responseBody = await backendResponse.arrayBuffer();
      const responseHeaders: Record<string, string> = {
        "Content-Type": responseContentType,
      };
      const contentDisposition =
        backendResponse.headers.get("Content-Disposition");
      if (contentDisposition) {
        responseHeaders["Content-Disposition"] = contentDisposition;
      }
      return new NextResponse(responseBody, {
        status: backendResponse.status,
        headers: responseHeaders,
      });
    }

    const responseBody = await backendResponse.text();
    return new NextResponse(responseBody, {
      status: backendResponse.status,
      headers: { "Content-Type": responseContentType },
    });
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context.params);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context.params);
}
