/**
 * Next.js proxy for POST /api/auth/local/token.
 *
 * Pass-through proxy that forwards local login requests to the backend.
 * The Credentials provider in auth.ts calls the backend directly (server-side),
 * so this proxy is mainly for completeness and future client-side use.
 *
 * Security: credentials are forwarded as-is; no token is stored client-side.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest): Promise<NextResponse> {
  try {
    const body = (await req.json()) as unknown;
    const res = await fetch(`${BACKEND_URL}/api/auth/local/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Failed to connect to authentication service" },
      { status: 502 }
    );
  }
}
