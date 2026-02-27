// frontend/src/app/api/channels/accounts/[id]/route.ts
/**
 * Server-side proxy for DELETE /api/channels/accounts/{id}.
 * Injects the server-side Bearer token -- credentials never touch the browser.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAccessToken(): Promise<string | undefined> {
  const session = await auth();
  return (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;

  try {
    const res = await fetch(`${API_URL}/api/channels/accounts/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    });

    if (!res.ok && res.status !== 204) {
      return NextResponse.json(
        { error: "Failed to unlink account" },
        { status: res.status }
      );
    }

    return new NextResponse(null, { status: 204 });
  } catch {
    return NextResponse.json(
      { error: "Failed to unlink account" },
      { status: 500 }
    );
  }
}
