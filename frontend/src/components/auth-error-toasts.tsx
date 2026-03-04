"use client";
/**
 * Auth error toast notifications + session error detection — Client Component.
 *
 * Detects two session loss scenarios:
 *
 * Scenario A — session.error from failed token refresh (SessionExpired,
 * RefreshAccessTokenError): The Keycloak refresh token expired while the
 * next-auth cookie still exists. The jwt callback sets session.error when
 * the refresh call fails.
 *
 * Scenario B — session transitions to unauthenticated while on a protected
 * page: The session cookie was deleted (e.g. another tab signed out, server-
 * side session was revoked, or the cookie expired). Detected by tracking the
 * status transition from "authenticated" → "unauthenticated" using a ref.
 *
 * In both cases: shows a toast, then after 1.5s calls signOut() to clear
 * any remaining next-auth state and redirects to /login with callbackUrl.
 *
 * SessionProvider must wrap this component (it uses useSession).
 * refetchInterval={300} and refetchOnWindowFocus={true} on SessionProvider
 * ensure periodic polling and multi-tab sync so Scenario B fires promptly.
 *
 * Skip detection on /login itself to avoid redirect loops.
 */
import { useEffect, useRef } from "react";
import { useSession, signOut } from "next-auth/react";
import { Toaster, toast } from "sonner";
import { usePathname } from "next/navigation";

export function AuthErrorToasts() {
  const { data: session, status } = useSession();
  const pathname = usePathname();
  const previousStatus = useRef(status);

  useEffect(() => {
    // Don't trigger on login page — would cause a redirect loop
    if (pathname === "/login") return;

    // Scenario A: session.error from failed token refresh
    if (
      session?.error === "SessionExpired" ||
      session?.error === "RefreshAccessTokenError"
    ) {
      toast.error("Your session has expired. Please sign in again.", {
        duration: 4000,
      });

      const timer = setTimeout(() => {
        void signOut({
          callbackUrl: `/login?callbackUrl=${encodeURIComponent(pathname)}&error=${session.error}`,
        });
      }, 1500);

      return () => clearTimeout(timer);
    }

    // Scenario B: session became null (cookie deleted, server-side invalidation)
    // Only trigger when transitioning FROM authenticated TO unauthenticated
    // (not on initial page load where status starts as "loading")
    if (
      status === "unauthenticated" &&
      previousStatus.current === "authenticated"
    ) {
      toast.error("Your session has expired. Please sign in again.", {
        duration: 4000,
      });

      const timer = setTimeout(() => {
        void signOut({
          callbackUrl: `/login?callbackUrl=${encodeURIComponent(pathname)}`,
        });
      }, 1500);

      return () => clearTimeout(timer);
    }

    previousStatus.current = status;
  }, [session?.error, status, pathname]);

  return <Toaster position="top-right" richColors />;
}
