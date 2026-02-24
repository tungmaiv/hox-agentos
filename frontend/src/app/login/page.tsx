"use client";
/**
 * Login page — initiates Keycloak OIDC flow immediately on mount.
 * Users are redirected here when unauthenticated.
 */
import { signIn } from "next-auth/react";
import { useEffect } from "react";

export default function LoginPage() {
  useEffect(() => {
    signIn("keycloak", { callbackUrl: "/chat" });
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-gray-500">Redirecting to login...</p>
    </div>
  );
}
