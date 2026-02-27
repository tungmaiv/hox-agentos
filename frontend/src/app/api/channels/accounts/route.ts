// frontend/src/app/api/channels/accounts/route.ts
/**
 * Server-side proxy for GET /api/channels/accounts.
 * Injects the server-side Bearer token -- credentials never touch the browser.
 */
import { auth } from "@/auth";
import { NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAccessToken(): Promise<string | undefined> {
  const session = await auth();
  return (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined;
}

export async function GET() {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json([], { status: 401 });
  }

  try {
    const res = await fetch(`${API_URL}/api/channels/accounts`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });

    if (!res.ok) {
      return NextResponse.json([]);
    }

    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json([]);
  }
}
