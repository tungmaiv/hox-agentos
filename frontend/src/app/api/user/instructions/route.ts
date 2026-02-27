// frontend/src/app/api/user/instructions/route.ts
/**
 * Server-side proxy for GET/PUT /api/user/instructions/.
 * Injects the server-side Bearer token — credentials never touch the browser.
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
  if (!accessToken)
    return NextResponse.json(
      { instructions: "", updated_at: "" },
      { status: 401 }
    );

  try {
    const res = await fetch(`${API_URL}/api/user/instructions/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (!res.ok)
      return NextResponse.json({ instructions: "", updated_at: "" });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ instructions: "", updated_at: "" });
  }
}

export async function PUT(request: Request) {
  const accessToken = await getAccessToken();
  if (!accessToken)
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const body = await request.json() as unknown;
    const res = await fetch(`${API_URL}/api/user/instructions/`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok)
      return NextResponse.json(
        { error: "Failed to save" },
        { status: res.status }
      );
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "Failed to save" }, { status: 500 });
  }
}
