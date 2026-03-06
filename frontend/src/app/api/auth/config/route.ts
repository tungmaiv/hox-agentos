/**
 * Next.js proxy for GET /api/auth/config.
 * Forwards to backend and returns auth mode (local-only or local+keycloak).
 * Public — no JWT required.
 */
import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function GET(): Promise<NextResponse> {
  try {
    const res = await fetch(`${BACKEND_URL}/api/auth/config`, {
      cache: "no-store",
    });
    const data = (await res.json()) as unknown;
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ auth: "local-only", sso_enabled: false });
  }
}
