"use client";
/**
 * Admin Identity page — Keycloak SSO configuration.
 *
 * Allows admins to:
 * 1. View current SSO status (local-only vs keycloak enabled)
 * 2. Test Keycloak connection before saving
 * 3. Configure Keycloak (Issuer URL, Client ID, Client Secret, Realm, CA Cert)
 * 4. Save & Apply — saves to backend DB + triggers frontend restart
 * 5. Disable SSO — reverts to local-only mode (with confirmation dialog)
 *
 * Client secret field: shows "Change secret" toggle when has_secret=true.
 *   Expanding the toggle reveals an empty input (never reveals the saved secret).
 *   The backend GET response only returns has_secret: bool — never the raw value.
 *
 * Uses POST /api/admin/keycloak/* proxy routes (auth forwarded via server session).
 */

import { useEffect, useState } from "react";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const KeycloakConfigSchema = z.object({
  configured: z.boolean(),
  issuer_url: z.string().default(""),
  client_id: z.string().default(""),
  has_secret: z.boolean().default(false), // true if a secret is stored; never the secret itself
  realm: z.string().default(""),
  ca_cert_path: z.string().default(""),
  enabled: z.boolean().default(false),
});

type KeycloakConfig = z.infer<typeof KeycloakConfigSchema>;

const TestConnectionSchema = z.object({
  reachable: z.boolean(),
  keys_found: z.number().default(0),
  error: z.string().nullable().default(null),
});

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function fetchConfig(): Promise<KeycloakConfig | null> {
  const res = await fetch("/api/admin/keycloak/config");
  if (!res.ok) return null;
  return KeycloakConfigSchema.parse(await res.json());
}

async function testConnection(
  issuerUrl: string,
  caCertPath: string
): Promise<z.infer<typeof TestConnectionSchema>> {
  const res = await fetch("/api/admin/keycloak/test-connection", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ issuer_url: issuerUrl, ca_cert_path: caCertPath }),
  });
  return TestConnectionSchema.parse(await res.json());
}

async function saveConfig(config: {
  issuer_url: string;
  client_id: string;
  client_secret: string;
  realm: string;
  ca_cert_path: string;
}): Promise<boolean> {
  const res = await fetch("/api/admin/keycloak/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  return res.ok;
}

async function disableSSO(): Promise<boolean> {
  const res = await fetch("/api/admin/keycloak/disable", { method: "POST" });
  return res.ok;
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

type LoadState = "loading" | "forbidden" | "error" | "ready";
type TestState = "idle" | "testing" | "success" | "failed";
type SaveState = "idle" | "saving" | "saved" | "error";

export default function AdminIdentityPage() {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [config, setConfig] = useState<KeycloakConfig | null>(null);

  // Form fields
  const [issuerUrl, setIssuerUrl] = useState("");
  const [clientId, setClientId] = useState("");
  const [realm, setRealm] = useState("");
  const [caCertPath, setCaCertPath] = useState("");

  // Secret field: "Change secret" expand toggle
  // When has_secret=true from backend, we show a toggle instead of an always-visible input.
  // Expanding the toggle reveals a new empty input — we never show the saved secret.
  const [showChangeSecret, setShowChangeSecret] = useState(false);
  const [newClientSecret, setNewClientSecret] = useState("");

  // Action state
  const [testState, setTestState] = useState<TestState>("idle");
  const [testResult, setTestResult] = useState<z.infer<
    typeof TestConnectionSchema
  > | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [showDisableConfirm, setShowDisableConfirm] = useState(false);
  const [disabling, setDisabling] = useState(false);

  // ---------------------------------------------------------------------------
  // Load current config
  // ---------------------------------------------------------------------------

  useEffect(() => {
    void (async () => {
      try {
        const cfg = await fetchConfig();
        if (cfg === null) {
          setLoadState("error");
          return;
        }
        setConfig(cfg);
        if (cfg.configured) {
          setIssuerUrl(cfg.issuer_url);
          setClientId(cfg.client_id);
          setRealm(cfg.realm);
          setCaCertPath(cfg.ca_cert_path);
          // has_secret: if true, show toggle; don't pre-fill newClientSecret
          setShowChangeSecret(!cfg.has_secret); // Show input directly if no secret exists yet
        }
        setLoadState("ready");
      } catch {
        setLoadState("error");
      }
    })();
  }, []);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  async function handleTestConnection(): Promise<void> {
    setTestState("testing");
    setTestResult(null);
    try {
      const result = await testConnection(issuerUrl, caCertPath);
      setTestResult(result);
      setTestState(result.reachable ? "success" : "failed");
    } catch {
      setTestState("failed");
      setTestResult({ reachable: false, keys_found: 0, error: "Request failed" });
    }
  }

  async function handleSave(): Promise<void> {
    setSaveState("saving");
    // If has_secret=true and toggle not expanded, keep existing secret (send empty → backend skips update)
    // Backend should handle empty client_secret as "keep existing" when a secret is already stored.
    // If no secret was stored, client_secret is required.
    const secretToSend = showChangeSecret ? newClientSecret : "";
    try {
      const ok = await saveConfig({
        issuer_url: issuerUrl,
        client_id: clientId,
        client_secret: secretToSend,
        realm,
        ca_cert_path: caCertPath,
      });
      setSaveState(ok ? "saved" : "error");
      if (ok) {
        const cfg = await fetchConfig();
        if (cfg) {
          setConfig(cfg);
          // Reset secret toggle after successful save
          setShowChangeSecret(!cfg.has_secret);
          setNewClientSecret("");
        }
      }
    } catch {
      setSaveState("error");
    }
  }

  async function handleDisable(): Promise<void> {
    setDisabling(true);
    try {
      const ok = await disableSSO();
      if (ok) {
        setShowDisableConfirm(false);
        const cfg = await fetchConfig();
        if (cfg) setConfig(cfg);
      }
    } finally {
      setDisabling(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loadState === "loading") {
    return (
      <p className="text-sm text-gray-500">Loading identity configuration...</p>
    );
  }

  if (loadState === "error") {
    return (
      <p className="text-sm text-red-600">
        Failed to load identity configuration. Check admin permissions.
      </p>
    );
  }

  const isConfigured = config?.configured === true;
  const isSSOActive = isConfigured && config?.enabled === true;
  const hasExistingSecret = config?.has_secret === true;

  // Save button disabled when: required fields missing, OR secret required but not provided
  const secretReady = hasExistingSecret
    ? !showChangeSecret || newClientSecret.length > 0 // toggle not expanded, OR expanded with value
    : newClientSecret.length > 0; // no existing secret → must provide one
  const canSave =
    saveState !== "saving" && issuerUrl && clientId && realm && secretReady;

  return (
    <div className="max-w-2xl space-y-8">
      {/* Status badge */}
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold text-gray-900">
          Identity Configuration
        </h2>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            isSSOActive
              ? "bg-green-100 text-green-800"
              : "bg-gray-100 text-gray-600"
          }`}
        >
          {isSSOActive ? "SSO Active" : "Local-only"}
        </span>
      </div>

      {/* Keycloak config form */}
      <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-900">
          Keycloak SSO Configuration
        </h3>

        <div className="space-y-4">
          <Field
            label="Issuer URL"
            id="issuer_url"
            value={issuerUrl}
            onChange={setIssuerUrl}
            placeholder="https://keycloak.blitz.local/realms/blitz-internal"
            hint="The full issuer URL including realm path."
          />
          <Field
            label="Client ID"
            id="client_id"
            value={clientId}
            onChange={setClientId}
            placeholder="blitz-portal"
          />

          {/* Client Secret — "Change secret" toggle pattern */}
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Client Secret
            </label>
            {hasExistingSecret && !showChangeSecret ? (
              <div className="mt-1 flex items-center gap-3">
                <span className="text-sm text-gray-500">
                  Secret is configured
                </span>
                <button
                  type="button"
                  onClick={() => setShowChangeSecret(true)}
                  className="text-sm text-blue-600 underline hover:text-blue-800"
                >
                  Change secret
                </button>
              </div>
            ) : (
              <div className="mt-1">
                <input
                  id="client_secret"
                  type="password"
                  value={newClientSecret}
                  onChange={(e) => setNewClientSecret(e.target.value)}
                  placeholder={
                    hasExistingSecret
                      ? "Enter new secret to replace current"
                      : "Enter client secret"
                  }
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                {hasExistingSecret && (
                  <button
                    type="button"
                    onClick={() => {
                      setShowChangeSecret(false);
                      setNewClientSecret("");
                    }}
                    className="mt-1 text-xs text-gray-500 underline hover:text-gray-700"
                  >
                    Keep current secret
                  </button>
                )}
              </div>
            )}
          </div>

          <Field
            label="Realm"
            id="realm"
            value={realm}
            onChange={setRealm}
            placeholder="blitz-internal"
          />
          <Field
            label="CA Cert Path (optional)"
            id="ca_cert_path"
            value={caCertPath}
            onChange={setCaCertPath}
            placeholder="/certs/keycloak-ca.crt"
            hint="Path to CA cert for self-signed TLS. Leave blank for trusted CA."
          />
        </div>

        {/* Test connection result — inline, not toast */}
        {testResult && (
          <div
            className={`mt-4 rounded-md p-3 text-sm ${
              testResult.reachable
                ? "border border-green-200 bg-green-50 text-green-800"
                : "border border-red-200 bg-red-50 text-red-800"
            }`}
          >
            {testResult.reachable
              ? `Connected — JWKS endpoint reachable, ${testResult.keys_found} key(s) found.`
              : `Connection failed: ${testResult.error ?? "Unknown error"}`}
          </div>
        )}

        {/* Save feedback */}
        {saveState === "saved" && (
          <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
            Configuration saved. Frontend is restarting — SSO will be available
            in ~30 seconds.
          </div>
        )}
        {saveState === "error" && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            Failed to save configuration. Check admin permissions and backend
            logs.
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex gap-3">
          <button
            type="button"
            disabled={testState === "testing" || !issuerUrl}
            onClick={() => void handleTestConnection()}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {testState === "testing" ? "Testing..." : "Test Connection"}
          </button>

          <button
            type="button"
            disabled={!canSave}
            onClick={() => void handleSave()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saveState === "saving" ? "Saving..." : "Save & Apply"}
          </button>
        </div>
      </section>

      {/* Disable SSO section */}
      {isSSOActive && (
        <section className="rounded-lg border border-red-200 bg-white p-6 shadow-sm">
          <h3 className="mb-1 text-sm font-medium text-gray-900">
            Disable SSO
          </h3>
          <p className="mb-4 text-sm text-gray-500">
            Disabling SSO reverts to local-only authentication. Existing SSO
            configuration is preserved and can be re-enabled later.
          </p>

          {!showDisableConfirm ? (
            <button
              type="button"
              onClick={() => setShowDisableConfirm(true)}
              className="rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 shadow-sm hover:bg-red-50"
            >
              Disable SSO
            </button>
          ) : (
            <div className="rounded-md border border-red-300 bg-red-50 p-4">
              {/*
                LOCKED confirmation dialog text (CONTEXT.md → SSO disable behavior):
                "Disabling SSO will prevent new Keycloak logins. Users currently logged in
                via SSO will remain logged in until their session expires. Continue?"
              */}
              <p className="mb-3 text-sm font-medium text-red-800">
                Disabling SSO will prevent new Keycloak logins. Users currently
                logged in via SSO will remain logged in until their session
                expires. Continue?
              </p>
              <div className="flex gap-3">
                <button
                  type="button"
                  disabled={disabling}
                  onClick={() => void handleDisable()}
                  className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
                >
                  {disabling ? "Disabling..." : "Yes, Disable SSO"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowDisableConfirm(false)}
                  className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared field component
// ---------------------------------------------------------------------------

function Field({
  label,
  id,
  value,
  onChange,
  placeholder,
  hint,
  type = "text",
}: {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  hint?: string;
  type?: "text" | "password";
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  );
}
