/**
 * Server-side auth utilities for Next.js API routes.
 * These functions run only in server context (Route Handlers, Server Components).
 */
import { auth } from "@/auth";

/**
 * Extract the backend access token from the server-side session.
 * Returns null if no session exists or the token is not present.
 */
export async function getAccessToken(): Promise<string | null> {
  const session = await auth();
  if (!session) return null;
  return session.accessToken ?? null;
}
