/**
 * CopilotKit proxy — forwards AG-UI requests to FastAPI with server-side JWT.
 *
 * Security model:
 * - Reads access token from next-auth server-side session (never from browser)
 * - Token injected in Authorization header before forwarding to backend
 * - Token never serialized to browser cookies or returned to client
 *
 * The frontend calls /api/copilotkit (same-origin).
 * This route calls http://localhost:8000/api/copilotkit (with JWT).
 * The browser never sees the JWT.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest): Promise<NextResponse> {
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

  const body = await request.text();

  const backendResponse = await fetch(`${API_URL}/api/copilotkit`, {
    method: "POST",
    headers: {
      "Content-Type":
        request.headers.get("Content-Type") ?? "application/json",
      Authorization: `Bearer ${accessToken}`,
      // Forward CopilotKit protocol headers
      ...(request.headers.get("X-CopilotKit-Runtime-Client-GQL-Version")
        ? {
            "X-CopilotKit-Runtime-Client-GQL-Version":
              request.headers.get(
                "X-CopilotKit-Runtime-Client-GQL-Version"
              )!,
          }
        : {}),
    },
    body,
  });

  // Stream the response back (SSE / streaming text).
  // Only forward Transfer-Encoding when the backend sets it — an empty
  // Transfer-Encoding header is invalid HTTP and can cause fetch failures.
  const responseHeaders: Record<string, string> = {
    "Content-Type":
      backendResponse.headers.get("Content-Type") ?? "text/event-stream",
    "Cache-Control": "no-cache",
  };
  const transferEncoding = backendResponse.headers.get("Transfer-Encoding");
  if (transferEncoding) {
    responseHeaders["Transfer-Encoding"] = transferEncoding;
  }

  return new NextResponse(backendResponse.body, {
    status: backendResponse.status,
    headers: responseHeaders,
  });
}
