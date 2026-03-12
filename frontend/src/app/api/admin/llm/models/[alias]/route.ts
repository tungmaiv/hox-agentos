/**
 * Next.js API proxy for DELETE /api/admin/llm/models/{alias}.
 */
import { auth } from "@/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ alias: string }> }
): Promise<NextResponse> {
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  if (!accessToken) {
    return NextResponse.json({ error: "No access token" }, { status: 401 });
  }

  const { alias } = await params;

  const backendRes = await fetch(
    `${BACKEND_URL}/api/admin/llm/models/${encodeURIComponent(alias)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    }
  );

  if (backendRes.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const data: unknown = await backendRes.json().catch(() => ({}));
  return NextResponse.json(data, { status: backendRes.status });
}
