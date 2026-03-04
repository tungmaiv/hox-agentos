"use client";
/**
 * Auth error toast notifications + session error detection — Client Component.
 *
 * Detects session errors from next-auth (SessionExpired, RefreshAccessTokenError)
 * and auto-redirects to /login with a toast notification.
 *
 * Also renders the Sonner Toaster for all auth-related toasts.
 *
 * Flow:
 * 1. useSession() detects session.error (set in jwt callback when refresh fails)
 * 2. Shows error toast: "Your session has expired. Please sign in again."
 * 3. After 1.5s delay (for toast visibility), calls signOut() with redirect to
 *    /login?callbackUrl=<current-path>&error=<error-code>
 * 4. /login page reads callbackUrl to return user after re-login
 *
 * Skip detection on /login itself to avoid redirect loops.
 */
import { useEffect } from "react";
import { useSession, signOut } from "next-auth/react";
import { Toaster, toast } from "sonner";
import { usePathname } from "next/navigation";

export function AuthErrorToasts() {
  const { data: session } = useSession();
  const pathname = usePathname();

  useEffect(() => {
    // Don't trigger on login page — would cause a redirect loop
    if (pathname === "/login") return;

    if (
      session?.error === "SessionExpired" ||
      session?.error === "RefreshAccessTokenError"
    ) {
      // Show toast notification
      toast.error("Your session has expired. Please sign in again.", {
        duration: 4000,
      });

      // Auto-redirect to /login after a brief delay for toast visibility
      const timer = setTimeout(() => {
        void signOut({
          callbackUrl: `/login?callbackUrl=${encodeURIComponent(pathname)}&error=${session.error}`,
        });
      }, 1500);

      return () => clearTimeout(timer);
    }
  }, [session?.error, pathname]);

  return <Toaster position="top-right" richColors />;
}
