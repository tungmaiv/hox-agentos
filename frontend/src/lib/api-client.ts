/**
 * Server-side API client for Blitz AgentOS backend.
 *
 * Security policy:
 * - Access token is injected from the server-side next-auth session.
 * - The token is NEVER exposed to client-side JavaScript or browser cookies.
 * - Only use serverFetch() in Server Components and Server Actions.
 *
 * Usage (Server Component):
 *   import { serverFetch } from "@/lib/api-client";
 *   const data = await serverFetch<MyResponse>("/api/agents/chat", {
 *     method: "POST",
 *     body: JSON.stringify({ message: "Hello" }),
 *   });
 */

import { auth } from "@/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ApiClientOptions extends Omit<RequestInit, "headers"> {
  headers?: Record<string, string>;
}

export interface ApiError extends Error {
  status: number;
  body: unknown;
}

/**
 * Server-side fetch wrapper that injects the Authorization: Bearer header
 * from the next-auth JWT session.
 *
 * IMPORTANT: This function can only be used in Server Components and Server
 * Actions. It calls auth() which requires a server-side request context.
 * The access token is never sent to the browser.
 *
 * @param path - API path (e.g. "/api/agents/chat")
 * @param options - Fetch options (method, body, headers, etc.)
 * @returns Parsed JSON response typed as T
 * @throws ApiError if the response status is not 2xx
 * @throws Error("Not authenticated") if there is no active session
 */
// TODO: verify dead — serverFetch is not imported by any Server Component yet.
// Designed for use in Server Components that need JWT-authenticated backend calls.
// Safe to keep: low overhead, no side-effects. Remove if still unused after Phase 12.
export async function serverFetch<T>(
  path: string,
  options: ApiClientOptions = {}
): Promise<T> {
  const session = await auth();
  if (!session) {
    throw new Error("Not authenticated");
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers ?? {}),
  };

  // Access token is kept server-side only — injected here, never sent to browser
  const token = (session as { accessToken?: string }).accessToken;
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({
      detail: response.statusText,
    }));
    const error = Object.assign(
      new Error((body as { detail?: string }).detail ?? "API error"),
      { status: response.status, body }
    ) as ApiError;
    throw error;
  }

  return response.json() as Promise<T>;
}
