"use client";
/**
 * PasswordChangeCard — inline expandable form for changing password.
 *
 * Only rendered when authProvider === "credentials" (local auth users).
 * SSO users do not see this card — they manage passwords via Keycloak.
 *
 * UX: "Change Password" button reveals the form inline (not a modal).
 * Success: shows green message, collapses form.
 * Error: shows inline error message.
 */
import { useSession } from "next-auth/react";
import { useState } from "react";

export function PasswordChangeCard() {
  const { data: session } = useSession();
  const token = session as unknown as Record<string, unknown> | null;
  const authProvider = (token?.authProvider ?? "credentials") as
    | "keycloak"
    | "credentials";

  const [expanded, setExpanded] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Only render for local auth users
  if (authProvider !== "credentials") return null;

  function handleExpand() {
    setExpanded(true);
    setError(null);
    setSuccess(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
  }

  function handleCancel() {
    setExpanded(false);
    setError(null);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match");
      return;
    }

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }

    if (!/[A-Z]/.test(newPassword)) {
      setError("New password must contain at least one uppercase letter");
      return;
    }

    if (!/[a-z]/.test(newPassword)) {
      setError("New password must contain at least one lowercase letter");
      return;
    }

    if (!/\d/.test(newPassword)) {
      setError("New password must contain at least one digit");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/local/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (res.ok) {
        setSuccess(true);
        setExpanded(false);
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
        // Auto-hide success message after 3 seconds
        setTimeout(() => setSuccess(false), 3000);
      } else {
        const data = (await res.json()) as { detail?: string };
        setError(data.detail ?? "Failed to change password");
      }
    } catch {
      setError("Network error — please try again");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
      <h2 className="text-base font-semibold text-gray-900 mb-4">
        Change Password
      </h2>

      {success && (
        <div className="mb-4 flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-md px-3 py-2">
          <svg
            className="w-4 h-4 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          Password updated successfully
        </div>
      )}

      {!expanded ? (
        <button
          type="button"
          onClick={handleExpand}
          className="px-4 py-2 text-sm font-medium text-blue-600 border border-blue-300 rounded-md hover:bg-blue-50 transition-colors"
        >
          Change Password
        </button>
      ) : (
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
              {error}
            </p>
          )}

          <div>
            <label
              htmlFor="current-password"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Current password
            </label>
            <input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label
              htmlFor="new-password"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              New password
            </label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-400">
              Min 8 characters, one uppercase, one lowercase, one digit
            </p>
          </div>

          <div>
            <label
              htmlFor="confirm-password"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Confirm new password
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-md text-sm font-medium transition-colors"
            >
              {loading ? "Updating..." : "Update Password"}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
