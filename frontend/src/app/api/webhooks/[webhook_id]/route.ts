// frontend/src/app/api/webhooks/[webhook_id]/route.ts
/**
 * Server-side proxy for POST /api/webhooks/{webhook_id}.
 * Passes through the webhook request to the backend — no auth injection needed
 * (backend validates X-Webhook-Secret header directly).
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ webhook_id: string }> }
): Promise<NextResponse> {
  const { webhook_id } = await params;
  const secret = req.headers.get("X-Webhook-Secret");

  try {
    const body = await req.text();
    const res = await fetch(`${BACKEND}/api/webhooks/${webhook_id}`, {
      method: "POST",
      headers: {
        "Content-Type": req.headers.get("Content-Type") ?? "application/json",
        ...(secret ? { "X-Webhook-Secret": secret } : {}),
      },
      body,
    });
    const data = (await res.json()) as unknown;
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Webhook delivery failed" }, { status: 500 });
  }
}
