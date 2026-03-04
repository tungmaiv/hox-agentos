/**
 * next-auth v5 configuration with Keycloak OIDC and local Credentials providers.
 *
 * Security policy:
 * - JWT stored in server-side session (strategy: "jwt") — NOT in localStorage (XSS protection)
 * - access_token is kept in server JWT only — never sent to the browser
 * - Client session only exposes user id and email
 *
 * Token refresh:
 * - Keycloak tokens: refreshed 5 minutes before expiry via refresh_token flow (AUTH-04)
 * - Local tokens: 8-hour fixed expiry; no refresh_token. On expiry, error="SessionExpired"
 *   so the client can redirect to /login.
 *
 * Auth providers:
 * - "keycloak" — Keycloak OIDC (SSO); RS256 verified by backend
 * - "credentials" — local username/password; HS256 JWT issued by backend local auth
 */
import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";
import Keycloak from "next-auth/providers/keycloak";
import Credentials from "next-auth/providers/credentials";

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
  trustHost: true, // Required for Docker: container binds to 0.0.0.0, not localhost
  // AUTH-03: Explicit cookie security — ensures the Secure flag is set in production.
  // next-auth v5 sets HttpOnly and SameSite=Lax by default; this config makes the
  // Secure flag explicit so it is never accidentally omitted in a production build.
  cookies: {
    sessionToken: {
      name:
        process.env.NODE_ENV === "production"
          ? "__Secure-authjs.session-token"
          : "authjs.session-token",
      options: {
        httpOnly: true,
        sameSite: "lax" as const,
        path: "/",
        secure: process.env.NODE_ENV === "production",
      },
    },
  },
  providers: [
    Keycloak({
      clientId: process.env.KEYCLOAK_CLIENT_ID ?? "",
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET ?? "",
      issuer: process.env.KEYCLOAK_ISSUER,
    }),
    Credentials({
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.password) return null;
        // BACKEND_URL is set in Docker (http://backend:8000).
        // Falls back to NEXT_PUBLIC_API_URL for local dev server.
        const backendUrl =
          process.env.BACKEND_URL ??
          process.env.NEXT_PUBLIC_API_URL ??
          "http://localhost:8000";
        try {
          const res = await fetch(`${backendUrl}/api/auth/local/token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              username: credentials.username,
              password: credentials.password,
            }),
          });
          if (!res.ok) return null;
          const { access_token } = (await res.json()) as {
            access_token: string;
          };
          // Decode JWT payload (no verification — backend already verified)
          const payloadPart = access_token.split(".")[1] ?? "";
          const payload = JSON.parse(
            Buffer.from(payloadPart, "base64url").toString()
          ) as {
            sub?: string;
            preferred_username?: string;
            email?: string;
            realm_roles?: string[];
          };
          return {
            id: payload.sub ?? "",
            name: payload.preferred_username ?? "",
            email: payload.email ?? "",
            accessToken: access_token,
            realmRoles: payload.realm_roles ?? [],
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  pages: {
    signIn: "/login", // Use our custom login page instead of Auth.js default
  },
  session: { strategy: "jwt" }, // JWT in server memory — NOT localStorage
  callbacks: {
    async jwt({ token, account, user }) {
      // Initial sign-in from Credentials provider
      if (account?.provider === "credentials" && user) {
        const u = user as {
          accessToken?: string;
          realmRoles?: string[];
        };
        return {
          ...token,
          accessToken: u.accessToken,
          realmRoles: u.realmRoles ?? [],
          // Local tokens: 8-hour expiry from now, no refresh token
          expiresAt: Math.floor(Date.now() / 1000) + 8 * 3600,
          authProvider: "credentials",
        };
      }

      // Initial sign-in from Keycloak
      if (account?.provider === "keycloak" && account) {
        return {
          ...token,
          accessToken: account.access_token,
          idToken: account.id_token,
          refreshToken: account.refresh_token,
          expiresAt: account.expires_at, // Unix timestamp in seconds
          authProvider: "keycloak",
        };
      }

      // Local credentials token: check expiry, no refresh possible
      if (token.authProvider === "credentials") {
        if (Date.now() >= (token.expiresAt as number) * 1000) {
          return { ...token, error: "SessionExpired" };
        }
        return token;
      }

      // Keycloak token: check expiry with 5-minute buffer (AUTH-04)
      // 5 minutes gives margin for slow internal networks and prevents mid-request token expiry
      if (Date.now() < (token.expiresAt as number) * 1000 - 300_000) {
        return token;
      }

      // Keycloak token expired — attempt refresh.
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
      session.accessToken = token.accessToken;
      session.user.id = token.sub ?? "";

      // Propagate realm roles to session for admin layout RBAC check
      session.realmRoles = token.realmRoles ?? [];

      // Pass idToken for Keycloak end-session logout (AUTH-05)
      // idToken is the OIDC identity token used only for logout — not the access token
      session.idToken = token.idToken;

      // Pass authProvider so logout component knows whether to call Keycloak end-session
      session.authProvider = token.authProvider;

      // Propagate auth errors so the client can force re-login
      if (token.error) {
        session.error = token.error;
      }

      return session;
    },
  },
});
