"use client";
/**
 * AccountInfoCard — displays user identity and session info on the profile page.
 *
 * Shows: name, email, auth provider badge (SSO or Local), roles as badges,
 * and session expiry as relative time ("Expires in 6h 42m", updates every minute).
 *
 * Reads expiresAt from the JWT token via useSession() — it is available on the
 * next-auth/jwt JWT type as expiresAt (Unix timestamp in seconds).
 */
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

function formatTimeRemaining(expiresAtSeconds: number): string {
  const now = Math.floor(Date.now() / 1000);
  const remaining = expiresAtSeconds - now;

  if (remaining <= 0) return "Expired";

  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);

  if (hours > 0) {
    return `Expires in ${hours}h ${minutes}m`;
  }
  return `Expires in ${minutes}m`;
}

export function AccountInfoCard() {
  const { data: session } = useSession();
  const [timeRemaining, setTimeRemaining] = useState<string>("");

  // Access token expiry from the JWT token extended fields
  const token = session as unknown as Record<string, unknown> | null;
  const expiresAt = token?.expiresAt as number | undefined;
  const realmRoles = (token?.realmRoles ?? []) as string[];
  const authProvider = (token?.authProvider ?? "credentials") as
    | "keycloak"
    | "credentials";

  useEffect(() => {
    if (!expiresAt) return;

    // Compute immediately
    setTimeRemaining(formatTimeRemaining(expiresAt));

    // Update every 60 seconds
    const interval = setInterval(() => {
      setTimeRemaining(formatTimeRemaining(expiresAt));
    }, 60_000);

    return () => clearInterval(interval);
  }, [expiresAt]);

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
      <h2 className="text-base font-semibold text-gray-900 mb-4">
        Account Information
      </h2>

      <div className="space-y-3">
        {/* Name */}
        {session?.user?.name && (
          <div className="flex items-start justify-between">
            <span className="text-sm text-gray-500 w-24 shrink-0">Name</span>
            <span className="text-sm text-gray-900 font-medium text-right">
              {session.user.name}
            </span>
          </div>
        )}

        {/* Email */}
        {session?.user?.email && (
          <div className="flex items-start justify-between">
            <span className="text-sm text-gray-500 w-24 shrink-0">Email</span>
            <span className="text-sm text-gray-900 text-right break-all">
              {session.user.email}
            </span>
          </div>
        )}

        {/* Auth provider badge */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500 w-24 shrink-0">
            Auth method
          </span>
          {authProvider === "keycloak" ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
              SSO
            </span>
          ) : (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              Local
            </span>
          )}
        </div>

        {/* Roles */}
        {realmRoles.length > 0 && (
          <div className="flex items-start justify-between">
            <span className="text-sm text-gray-500 w-24 shrink-0 pt-0.5">
              Roles
            </span>
            <div className="flex flex-wrap gap-1 justify-end">
              {realmRoles.map((role) => (
                <span
                  key={role}
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
                >
                  {role}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Session expiry */}
        {timeRemaining && (
          <div className="flex items-center justify-between pt-1 border-t border-gray-100">
            <span className="text-sm text-gray-500 w-24 shrink-0">Session</span>
            <span className="text-xs text-gray-400">{timeRemaining}</span>
          </div>
        )}
      </div>
    </div>
  );
}
