// frontend/src/app/api/conversations/[id]/title/route.ts
/**
 * Server-side proxy for PATCH /api/conversations/{id}/title.
 * Injects the server-side Bearer token — credentials never touch the browser.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

const API_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const session = await auth();
  if (!session)
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  if (!accessToken)
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const body = await request.json() as unknown;
    const res = await fetch(
      `${API_URL}/api/conversations/${id}/title`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(body),
      }
    );
    if (!res.ok)
      return NextResponse.json(
        { error: "Failed to rename" },
        { status: res.status }
      );
    return new NextResponse(null, { status: 204 });
  } catch {
    return NextResponse.json({ error: "Failed to rename" }, { status: 500 });
  }
}
