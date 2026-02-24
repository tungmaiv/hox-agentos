"use client";
/**
 * Auth error toast notifications — Client Component.
 *
 * Renders the Sonner Toaster so it is available for auth error notifications:
 * - 401 errors: "Session expired, re-authenticating..."
 * - 403 errors: "You don't have permission for this action"
 *
 * In Phase 2, this component will subscribe to API call error events via a
 * context and trigger the appropriate toast message.
 *
 * For Phase 1, it simply renders the Toaster at the app root level.
 */
import { Toaster } from "sonner";

export function AuthErrorToasts() {
  return <Toaster position="top-right" richColors />;
}
