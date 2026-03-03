// frontend/src/app/admin/credentials/page.tsx
"use client";

/**
 * Admin Credentials page — all-users OAuth connection view with admin force-revoke.
 *
 * Lives at /admin/credentials (part of the unified admin dashboard).
 * Admin layout provides the nav, padding, and role gate — no back-link needed here.
 *
 * Optimistic revoke: row removed immediately; failure restores it with error message.
 * Token values are NEVER returned from the backend — only metadata is shown.
 */

import { useEffect, useState, useCallback } from "react";
import { z } from "zod";

const CredentialSchema = z.object({
  user_id: z.string(),
  provider: z.string(),
  connected_at: z.string(),
});
type Credential = z.infer<typeof CredentialSchema>;

export default function AdminCredentialsPage() {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null); // key = `${user_id}:${provider}`
  const [revertItem, setRevertItem] = useState<Credential | null>(null);
  const [revertError, setRevertError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/credentials", { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) {
          setError("Failed to load credentials");
          return;
        }
        const raw: unknown = await res.json();
        const parsed = z.array(CredentialSchema).safeParse(raw);
        if (parsed.success) setCredentials(parsed.data);
        else setError("Invalid response from server");
      })
      .catch(() => setError("Network error"))
      .finally(() => setLoading(false));
  }, []);

  const handleRevoke = useCallback(async (cred: Credential) => {
    const key = `${cred.user_id}:${cred.provider}`;
    // Optimistic: remove immediately
    setCredentials((prev) =>
      prev.filter(
        (c) => !(c.user_id === cred.user_id && c.provider === cred.provider)
      )
    );
    setRevoking(key);
    setRevertError(null);

    try {
      const res = await fetch(
        `/api/admin/credentials/${encodeURIComponent(cred.user_id)}/${encodeURIComponent(cred.provider)}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (err) {
      // Revert: restore the item
      setCredentials((prev) => [cred, ...prev]);
      setRevertItem(cred);
      setRevertError(
        `Failed to revoke ${cred.provider} for ${cred.user_id} — ${err instanceof Error ? err.message : "unknown error"}`
      );
      setTimeout(() => {
        setRevertItem(null);
        setRevertError(null);
      }, 5000);
    } finally {
      setRevoking(null);
    }
  }, []);

  if (loading)
    return <div className="text-gray-500 py-8">Loading credentials...</div>;
  if (error) return <div className="text-red-600 py-8">{error}</div>;

  return (
    <div>
      <h2 className="text-lg font-semibold mb-2">OAuth Credentials</h2>
      <p className="text-sm text-gray-500 mb-6">
        All connected OAuth providers across users. Revoke removes the
        credential immediately. Users will need to reconnect via Settings &rarr;
        Channel Linking.
      </p>

      {revertError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
          {revertError}
        </div>
      )}

      {credentials.length === 0 ? (
        <p className="text-gray-400 text-sm">No OAuth credentials connected.</p>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  User ID
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Provider
                </th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">
                  Connected At
                </th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {credentials.map((cred) => {
                const key = `${cred.user_id}:${cred.provider}`;
                const isReverting =
                  revertItem?.user_id === cred.user_id &&
                  revertItem?.provider === cred.provider;
                return (
                  <tr
                    key={key}
                    className={isReverting ? "bg-red-50" : "hover:bg-gray-50"}
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 max-w-[200px] truncate">
                      {cred.user_id}
                    </td>
                    <td className="px-4 py-3 text-gray-900 capitalize">
                      {cred.provider}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(cred.connected_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => void handleRevoke(cred)}
                        disabled={revoking === key}
                        className="text-xs px-3 py-1.5 bg-red-50 text-red-700 border border-red-200 rounded hover:bg-red-100 disabled:opacity-50"
                      >
                        {revoking === key ? "Revoking..." : "Revoke"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
