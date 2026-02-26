// frontend/src/app/api/conversations/route.ts
/**
 * Server-side proxy for /api/conversations.
 *
 * Used by ChatLayout (client component) to refresh the conversation list
 * after each AI response. Runs server-side so the access token is never
 * exposed to the browser.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export async function GET() {
  const session = await auth();
  if (!session) return NextResponse.json([], { status: 401 });

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  if (!accessToken) return NextResponse.json([]);

  const apiUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${apiUrl}/api/conversations/?limit=20`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (!response.ok) return NextResponse.json([]);
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json([]);
  }
}
