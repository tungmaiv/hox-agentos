/**
 * Next.js proxy for DELETE /api/admin/local/users/{id}/roles/{role}.
 * Removes a direct role assignment from a user.
 */

import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAccessToken(): Promise<string | null> {
  const session = await auth();
  if (!session) return null;
  return (session as unknown as Record<string, unknown>)
    .accessToken as string | null;
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string; role: string }> }
): Promise<NextResponse> {
  const token = await getAccessToken();
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id, role } = await params;
  try {
    const res = await fetch(
      `${API}/api/admin/local/users/${id}/roles/${role}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (res.status === 204) {
      return new NextResponse(null, { status: 204 });
    }
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to remove role" },
      { status: 500 }
    );
  }
}
