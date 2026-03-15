"use client";
/**
 * Login page — dual sign-in: Keycloak SSO button + local credentials form.
 *
 * Users are redirected here when unauthenticated, or when their session expires.
 * - SSO button: triggers Keycloak OIDC flow (shown only when sso_enabled=true per backend)
 * - Credentials form: calls signIn("credentials") with username/password
 *
 * Supports:
 * - callbackUrl: returns user to their previous page after re-login (AUTH-06)
 * - signedOut=true: shows "You have been signed out successfully." banner (AUTH-05)
 * - error param: shows session expired notice (existing behavior)
 *
 * SSO button visibility (IDCFG-03):
 * - ssoEnabled=null (loading): button hidden
 * - ssoEnabled=false: button hidden
 * - ssoEnabled=true: button shown
 */
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, Suspense } from "react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlError = searchParams.get("error");
  const rawCallbackUrl = searchParams.get("callbackUrl") ?? "/chat";
  // Defense-in-depth: only allow relative paths to prevent open redirect
  const callbackUrl = rawCallbackUrl.startsWith("/") ? rawCallbackUrl : "/chat";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showSignedOut, setShowSignedOut] = useState(
    searchParams.get("signedOut") === "true"
  );

  // SSO state — null = loading (hidden), false = local-only (hidden), true = show SSO button
  const [ssoEnabled, setSsoEnabled] = useState<boolean | null>(null);
  // ssoAvailable: true when SSO is enabled AND circuit breaker is not open
  const [ssoAvailable, setSsoAvailable] = useState<boolean | null>(null);

  const sessionExpired =
    urlError === "SessionExpired" || urlError === "RefreshAccessTokenError";
  // SSOUnavailable: explicit circuit breaker redirect
  // OAuthCallbackError / OAuthSignin: next-auth catches Keycloak down mid-flow
  const ssoUnavailable =
    urlError === "SSOUnavailable" ||
    urlError === "OAuthCallbackError" ||
    urlError === "OAuthSignin";

  // Auto-dismiss the signed-out success banner after 3 seconds
  useEffect(() => {
    if (showSignedOut) {
      const timer = setTimeout(() => setShowSignedOut(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [showSignedOut]);

  // Fetch auth config to determine whether SSO button should be shown (IDCFG-03)
  // Also checks sso_available (false when circuit breaker is open)
  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/auth/config");
        if (res.ok) {
          const data = (await res.json()) as {
            sso_enabled?: boolean;
            sso_available?: boolean;
          };
          setSsoEnabled(data.sso_enabled === true);
          // sso_available defaults to sso_enabled when not present (backward compat)
          setSsoAvailable(data.sso_available ?? data.sso_enabled === true);
        } else {
          setSsoEnabled(false);
          setSsoAvailable(false);
        }
      } catch {
        setSsoEnabled(false);
        setSsoAvailable(false);
      }
    })();
  }, []);

  async function handleCredentialsSubmit(
    e: React.FormEvent<HTMLFormElement>
  ): Promise<void> {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await signIn("credentials", {
        username,
        password,
        redirect: false,
      });

      if (result?.error) {
        if (result.error === "CredentialsSignin") {
          setError("Invalid username or password. Please try again.");
        } else {
          // Non-credential error (e.g. stale CSRF token after server restart).
          // Reload the page to get a fresh CSRF token — the login will succeed
          // on the next attempt without the user needing to understand why.
          window.location.reload();
        }
      } else if (result?.ok) {
        router.push(callbackUrl);
      }
    } catch {
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleSSOSignIn(): void {
    void signIn("keycloak", { callbackUrl });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        {/* Logo / title */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900">Blitz AgentOS</h1>
          <p className="mt-1 text-sm text-gray-500">Sign in to continue</p>
        </div>

        {/* Signed-out success banner (auto-dismisses after 3 seconds) */}
        {showSignedOut && (
          <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
            You have been signed out successfully.
          </div>
        )}

        {/* Session expired notice */}
        {sessionExpired && (
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Your session has expired. Please sign in again.
          </div>
        )}

        {/* SSO mid-flow error — Keycloak was down during redirect */}
        {ssoUnavailable && (
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            SSO sign-in failed. Please try again or use your username and password.
          </div>
        )}

        {/* SSO temporarily unavailable — circuit breaker open */}
        {ssoEnabled === true && ssoAvailable === false && !ssoUnavailable && (
          <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
            SSO is temporarily unavailable. Please sign in with your username and password.
          </div>
        )}

        {/* Keycloak SSO button — shown only when ssoAvailable=true; hidden during loading (null) or when circuit breaker is open */}
        {ssoAvailable === true && (
          <button
            type="button"
            onClick={handleSSOSignIn}
            className="mb-6 flex w-full items-center justify-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            <svg
              className="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            Sign in with SSO
          </button>
        )}

        {/* Divider — only shown when SSO is available */}
        {ssoAvailable === true && (
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-gray-200" />
            </div>
            <div className="relative flex justify-center text-xs text-gray-400">
              <span className="bg-white px-2">or sign in with username</span>
            </div>
          </div>
        )}

        {/* Credentials form */}
        <form onSubmit={handleCredentialsSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-gray-700"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Enter your username"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Enter your password"
            />
          </div>

          {/* Inline error */}
          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <p className="text-gray-500">Loading...</p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
