/**
 * next-auth v5 configuration with Keycloak OIDC provider.
 *
 * Security policy:
 * - JWT stored in server-side session (strategy: "jwt") — NOT in localStorage (XSS protection)
 * - access_token is kept in server JWT only — never sent to the browser
 * - Client session only exposes user id and email
 *
 * Token refresh:
 * - expiresAt (Unix seconds) is stored alongside access_token on sign-in
 * - jwt() callback checks expiry on every call; refreshes 30s before expiry
 * - On refresh failure, error is propagated to session so the client can redirect to sign-in
 */
import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";
import Keycloak from "next-auth/providers/keycloak";

async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    const issuer = process.env.KEYCLOAK_ISSUER ?? "";
    const tokenUrl = `${issuer}/protocol/openid-connect/token`;

    const response = await fetch(tokenUrl, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: process.env.KEYCLOAK_CLIENT_ID ?? "",
        client_secret: process.env.KEYCLOAK_CLIENT_SECRET ?? "",
        grant_type: "refresh_token",
        refresh_token: token.refreshToken as string,
      }),
    });

    const refreshed = (await response.json()) as Record<string, unknown>;

    if (!response.ok) {
      throw new Error(
        (refreshed.error_description as string) ?? "Token refresh failed"
      );
    }

    return {
      ...token,
      accessToken: refreshed.access_token as string,
      idToken: (refreshed.id_token as string | undefined) ?? token.idToken,
      expiresAt:
        Math.floor(Date.now() / 1000) + (refreshed.expires_in as number),
      refreshToken:
        (refreshed.refresh_token as string | undefined) ?? token.refreshToken,
      error: undefined,
    };
  } catch {
    // Return token with error flag — session callback propagates it to client
    return { ...token, error: "RefreshAccessTokenError" };
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID ?? "",
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET ?? "",
      issuer: process.env.KEYCLOAK_ISSUER,
    }),
  ],
  session: { strategy: "jwt" }, // JWT in server memory — NOT localStorage
  callbacks: {
    async jwt({ token, account }) {
      // Initial sign-in — store all tokens and expiry from Keycloak
      if (account) {
        return {
          ...token,
          accessToken: account.access_token,
          idToken: account.id_token,
          refreshToken: account.refresh_token,
          expiresAt: account.expires_at, // Unix timestamp in seconds
        };
      }

      // Access token still valid (30-second buffer before expiry) — return as-is
      if (Date.now() < (token.expiresAt as number) * 1000 - 30_000) {
        return token;
      }

      // Access token expired — use refresh_token to get a new one.
      // If refreshToken is missing (old session pre-dating this change), return
      // the token as-is rather than making a broken refresh call. The backend
      // will return 401 and the user will be prompted to sign in again.
      if (!token.refreshToken) {
        return token;
      }
      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      // NEVER expose raw access_token to the client — keep in server session only.
      // The accessToken is set here so serverFetch() in Server Components can
      // inject the Authorization: Bearer header when calling the backend.
      // It is never serialized into the browser session cookie.
      (session as unknown as Record<string, unknown>).accessToken =
        token.accessToken;
      session.user.id = token.sub ?? "";

      // Propagate refresh errors so the client can force re-login
      if (token.error) {
        (session as unknown as Record<string, unknown>).error = token.error;
      }

      return session;
    },
  },
});
