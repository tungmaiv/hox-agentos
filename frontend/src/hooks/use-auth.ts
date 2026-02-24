"use client";
/**
 * OIDC authentication hook via next-auth v5.
 *
 * Wraps next-auth session management with Keycloak provider.
 * JWT is stored in server-side session — never in localStorage.
 */
import { useSession, signIn, signOut } from "next-auth/react";

export function useAuth() {
  const { data: session, status } = useSession();

  const login = () => signIn("keycloak");
  const logout = () => signOut({ callbackUrl: "/" });
  const isAuthenticated = status === "authenticated";
  const isLoading = status === "loading";

  return { session, isAuthenticated, isLoading, login, logout };
}
