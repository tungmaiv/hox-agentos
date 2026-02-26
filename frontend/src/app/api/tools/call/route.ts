/**
 * Server-side proxy for POST /api/tools/call.
 *
 * Injects the server-side Bearer token so credentials never touch the browser.
 * Forwards request body to backend POST /api/tools/call which enforces all
 * 3 security gates (JWT, RBAC, ACL).
 *
 * CLAUDE.md: `auth()` from next-auth v5; NEXT_PUBLIC_API_URL (not BACKEND_URL);
 * no `any`; Zod not needed here (we are a transparent proxy).
 */
import { auth } from "@/auth"
import { NextRequest, NextResponse } from "next/server"

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function getAccessToken(): Promise<string | undefined> {
  const session = await auth()
  return (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const accessToken = await getAccessToken()
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const body: unknown = await request.json()
    const response = await fetch(`${API_URL}/api/tools/call`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    })
    const data: unknown = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch {
    return NextResponse.json(
      { error: "Failed to call tool" },
      { status: 500 }
    )
  }
}
