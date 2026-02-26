// frontend/src/app/api/conversations/[id]/messages/route.ts
/**
 * Server-side proxy for /api/conversations/{id}/messages.
 * Fetches turn history for a conversation with the server-side access token.
 * Token is never exposed to the browser.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const session = await auth();
  if (!session) return NextResponse.json([], { status: 401 });

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  if (!accessToken) return NextResponse.json([]);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(
      `${apiUrl}/api/conversations/${id}/messages`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      }
    );
    if (!response.ok) return NextResponse.json([]);
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json([]);
  }
}
