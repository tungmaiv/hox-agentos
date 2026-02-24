/**
 * next-auth v5 configuration with Keycloak OIDC provider.
 *
 * Security policy:
 * - JWT stored in server-side session (strategy: "jwt") — NOT in localStorage (XSS protection)
 * - access_token is kept in server JWT only — never sent to the browser
 * - Client session only exposes user id and email
 */
import NextAuth from "next-auth";
import Keycloak from "next-auth/providers/keycloak";

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
      // Store access token in server-side JWT on initial sign-in
      if (account) {
        token.accessToken = account.access_token;
        token.idToken = account.id_token;
      }
      return token;
    },
    async session({ session, token }) {
      // NEVER expose raw access_token to the client — keep in server session only
      session.user.id = token.sub ?? "";
      return session;
    },
  },
});
