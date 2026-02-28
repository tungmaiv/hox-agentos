/**
 * Catch-all proxy for /api/admin/* backend routes.
 *
 * Forwards GET, POST, PUT, PATCH, DELETE requests to the backend
 * with JWT injection from the server-side next-auth session.
 * The access token is never exposed to the browser.
 *
 * Pattern: same as /api/copilotkit/route.ts and /api/conversations/route.ts.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    return NextResponse.json(
      { error: "No access token in session" },
      { status: 401 }
    );
  }

  const { path } = await params;
  const backendPath = `/api/admin/${path.join("/")}`;
  const url = new URL(backendPath, API_URL);

  // Forward query parameters
  const searchParams = request.nextUrl.searchParams;
  searchParams.forEach((value, key) => {
    url.searchParams.append(key, value);
  });

  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };

  // Forward Content-Type for requests with body
  const contentType = request.headers.get("Content-Type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }

  const fetchInit: RequestInit = {
    method: request.method,
    headers,
  };

  // Forward body for methods that have one
  if (["POST", "PUT", "PATCH"].includes(request.method)) {
    fetchInit.body = await request.text();
    if (!headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
  }

  try {
    const backendResponse = await fetch(url.toString(), fetchInit);
    const responseBody = await backendResponse.text();

    return new NextResponse(responseBody, {
      status: backendResponse.status,
      headers: {
        "Content-Type":
          backendResponse.headers.get("Content-Type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Backend unreachable" },
      { status: 502 }
    );
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

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context.params);
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context.params);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, context.params);
}
