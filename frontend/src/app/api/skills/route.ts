/**
 * Server-side proxy for /api/skills.
 *
 * Used by useSkills() hook (client component) to fetch available skills
 * for the /command menu in chat. Runs server-side so the access token
 * is never exposed to the browser.
 *
 * Pattern: same as /api/conversations/route.ts — proxy with JWT injection.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export async function GET() {
  const session = await auth();
  if (!session) return NextResponse.json([], { status: 401 });

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  if (!accessToken) return NextResponse.json([]);

  const apiUrl = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${apiUrl}/api/skills`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (!response.ok) return NextResponse.json([]);
    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json([]);
  }
}
