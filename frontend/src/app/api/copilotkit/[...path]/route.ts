/**
 * CopilotKit sub-path proxy — forwards AG-UI sub-route requests to FastAPI.
 *
 * Why this exists:
 *   CopilotKit REST transport (default) makes two types of requests:
 *     GET  {runtimeUrl}/info              — agent discovery
 *     POST {runtimeUrl}/agent/{name}/run  — agent execution (SSE streaming)
 *   The root route.ts only handles POST /api/copilotkit.
 *   This catch-all proxies all sub-paths with the same JWT injection.
 *
 * Security: identical model to route.ts — JWT from next-auth server session,
 * never from client headers or cookies.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function proxySubPath(
  request: NextRequest,
  pathSegments: string[]
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

  const subPath = pathSegments.join("/");
  const url = `${API_URL}/api/copilotkit/${subPath}`;

  const isGet = request.method === "GET";
  const body = isGet ? undefined : await request.text();

  const forwardHeaders: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };

  if (!isGet) {
    forwardHeaders["Content-Type"] =
      request.headers.get("Content-Type") ?? "application/json";
  }

  // Forward CopilotKit protocol version header if present
  const ckVersion = request.headers.get(
    "X-CopilotKit-Runtime-Client-GQL-Version"
  );
  if (ckVersion) {
    forwardHeaders["X-CopilotKit-Runtime-Client-GQL-Version"] = ckVersion;
  }

  const backendResponse = await fetch(url, {
    method: request.method,
    headers: forwardHeaders,
    ...(body !== undefined ? { body } : {}),
  });

  const contentType =
    backendResponse.headers.get("Content-Type") ?? "application/json";

  return new NextResponse(backendResponse.body, {
    status: backendResponse.status,
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "no-cache",
      ...(backendResponse.headers.get("Transfer-Encoding")
        ? {
            "Transfer-Encoding":
              backendResponse.headers.get("Transfer-Encoding")!,
          }
        : {}),
    },
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await params;
  return proxySubPath(request, path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await params;
  return proxySubPath(request, path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await params;
  return proxySubPath(request, path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await params;
  return proxySubPath(request, path);
}
