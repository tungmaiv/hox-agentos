// frontend/src/app/api/channels/pair/route.ts
/**
 * Server-side proxy for POST /api/channels/pair.
 * Injects the server-side Bearer token -- credentials never touch the browser.
 */
import { getAccessToken } from "@/lib/server-auth";
import { NextResponse } from "next/server";

const API_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(request: Request) {
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = (await request.json()) as unknown;
    const res = await fetch(`${API_URL}/api/channels/pair`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: "Failed to generate pairing code" },
        { status: res.status }
      );
    }

    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json(
      { error: "Failed to generate pairing code" },
      { status: 500 }
    );
  }
}
