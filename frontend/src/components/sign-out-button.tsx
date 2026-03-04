"use client";
/**
 * Sign-out button — Client Component (needs onClick event handler).
 *
 * For Keycloak SSO users (AUTH-05): calls Keycloak end-session endpoint to fully
 * revoke the SSO session server-side, then redirects to /login. This is critical
 * for shared office machines — partial logout (cookies only) leaves the Keycloak
 * session active.
 *
 * For local credentials users: clears next-auth cookies and redirects to /login.
 *
 * No confirmation dialog — click Sign Out → instant logout → redirect to /login.
 */
import { signOut, useSession } from "next-auth/react";

export function SignOutButton() {
  const { data: session } = useSession();

  async function handleSignOut(): Promise<void> {
    // For Keycloak users: call Keycloak end-session endpoint to fully revoke SSO session
    // This is critical for shared office machines — partial logout is a security risk
    if (session?.authProvider === "keycloak" && session?.idToken) {
      const keycloakIssuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER ?? "";
      if (keycloakIssuer) {
        const logoutUrl = new URL(
          `${keycloakIssuer}/protocol/openid-connect/logout`
        );
        logoutUrl.searchParams.set("id_token_hint", session.idToken);
        logoutUrl.searchParams.set(
          "post_logout_redirect_uri",
          `${window.location.origin}/login?signedOut=true`
        );

        // Clear next-auth session first, then redirect to Keycloak end-session
        await signOut({ redirect: false });
        window.location.href = logoutUrl.toString();
        return;
      }
    }

    // For local auth users (or if Keycloak issuer not configured):
    // Just clear next-auth cookies and redirect to /login
    await signOut({ callbackUrl: "/login?signedOut=true" });
  }

  return (
    <button
      onClick={() => void handleSignOut()}
      className="text-sm text-gray-500 hover:text-gray-900 transition-colors"
    >
      Sign out
    </button>
  );
}
