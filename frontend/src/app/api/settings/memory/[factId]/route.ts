/**
 * Server-side proxy for DELETE /api/user/memory/facts/{factId}.
 *
 * Proxies to backend DELETE /api/user/memory/facts/{fact_id}.
 * Backend enforces ownership check: fact.user_id == jwt_user_id.
 *
 * CLAUDE.md: use `auth()` from next-auth v5; NEXT_PUBLIC_API_URL.
 */
import { auth } from "@/auth"
import { NextRequest, NextResponse } from "next/server"

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function getAccessToken(): Promise<string | undefined> {
  const session = await auth()
  return (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ factId: string }> }
): Promise<NextResponse> {
  const accessToken = await getAccessToken()
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { factId } = await params

  try {
    const res = await fetch(
      `${API_URL}/api/user/memory/facts/${factId}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${accessToken}` },
      }
    )
    const data: unknown = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json(
      { error: "Failed to delete fact" },
      { status: 500 }
    )
  }
}
