"use client";
/**
 * Sign-out button — Client Component (needs onClick event handler).
 *
 * Triggers next-auth signOut() which clears the server-side session
 * and redirects back to the root URL (which redirects to Keycloak login).
 */
import { signOut } from "next-auth/react";

export function SignOutButton() {
  return (
    <button
      onClick={() => signOut({ callbackUrl: "/" })}
      className="text-sm text-gray-500 hover:text-gray-900 transition-colors"
    >
      Sign out
    </button>
  );
}
