/**
 * NextAuth v5 module augmentation to add custom fields to Session and JWT.
 *
 * This extends the default NextAuth types with the fields we add in auth.ts
 * session/jwt callbacks, eliminating the need for `as unknown as Record<string, unknown>`
 * casts in server components and route handlers.
 */
import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    /** Backend JWT — injected in session callback, kept server-side only */
    accessToken?: string;
    /** Keycloak/local realm roles propagated to session */
    realmRoles?: string[];
    /** Auth error: "RefreshAccessTokenError" | "SessionExpired" */
    error?: string;
    /** OIDC identity token — used only for Keycloak end-session logout (AUTH-05) */
    idToken?: string;
    /** Auth provider — "keycloak" or "credentials" — used for logout flow selection */
    authProvider?: "keycloak" | "credentials";
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string;
    idToken?: string;
    refreshToken?: string;
    expiresAt?: number;
    realmRoles?: string[];
    authProvider?: "keycloak" | "credentials";
    error?: string;
  }
}
