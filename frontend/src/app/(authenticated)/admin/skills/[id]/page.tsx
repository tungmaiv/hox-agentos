"use client";
/**
 * Admin skill detail page — /admin/skills/[id].
 *
 * Form-based editing with three tabs:
 * - Overview: read-only metadata + editable display name, description, status
 * - Config: skill-type-specific fields (instruction markdown, procedure JSON,
 *   slash command, category, tags, allowed tools) with markdown preview toggle
 * - Scan Results: existing security scan display preserved
 *
 * Uses RegistryDetailLayout for consistent shell with save bar.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { mapSnakeToCamel } from "@/lib/admin-types";
import type { RegistryEntry } from "@/lib/admin-types";
import { RegistryDetailLayout } from "@/components/admin/registry-detail-layout";
import { skillFormSchema, validateField } from "@/lib/registry-schemas";
import type { SkillFormValues } from "@/lib/registry-schemas";

// ---------------------------------------------------------------------------
// Security report type (matches backend SecurityScanResult schema)
// ---------------------------------------------------------------------------

interface SecurityReport {
  recommendation?: "approve" | "review" | "reject";
  scan_engine?: string;
  bandit_issues?: unknown[];
  pip_audit_issues?: unknown[];
  findings?: unknown[];
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "config", label: "Config" },
  { id: "scan-results", label: "Scan Results" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminSkillDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [entry, setEntry] = useState<RegistryEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  // Form state
  const [formData, setFormData] = useState<SkillFormValues>({
    displayName: null,
    description: null,
    skillType: "instructional",
    instructionMarkdown: null,
    slashCommand: null,
    category: null,
    tags: null,
    status: "active",
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>(
    {}
  );
  const initialFormRef = useRef<SkillFormValues | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Comma-separated string helpers for tags / allowedTools
  const [tagsStr, setTagsStr] = useState("");
  const [allowedToolsStr, setAllowedToolsStr] = useState("");

  // Markdown preview toggle
  const [previewMd, setPreviewMd] = useState(false);

  // Advanced raw JSON toggle + text
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [procedureJsonStr, setProcedureJsonStr] = useState("");

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    fetch(`/api/registry/${id}`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const raw = (await res.json()) as unknown;
        const mapped = mapSnakeToCamel<RegistryEntry>(
          raw as Record<string, unknown>
        );
        setEntry(mapped);
        initFormFromEntry(mapped);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load skill");
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const initFormFromEntry = useCallback((e: RegistryEntry) => {
    const cfg = e.config;
    const initial: SkillFormValues = {
      displayName: e.displayName ?? null,
      description: e.description ?? null,
      skillType:
        (cfg.skill_type as SkillFormValues["skillType"]) ?? "instructional",
      instructionMarkdown: (cfg.instruction_markdown as string) ?? null,
      slashCommand: (cfg.slash_command as string) ?? null,
      category: (cfg.category as string) ?? null,
      tags: (cfg.tags as string[]) ?? null,
      status: e.status as SkillFormValues["status"],
    };
    setFormData(initial);
    initialFormRef.current = initial;
    setTagsStr((cfg.tags as string[] | null)?.join(", ") ?? "");
    setAllowedToolsStr(
      (cfg.allowed_tools as string[] | null)?.join(", ") ?? ""
    );
    setProcedureJsonStr(
      cfg.procedure_json
        ? JSON.stringify(cfg.procedure_json, null, 2)
        : ""
    );
  }, []);

  // ---------------------------------------------------------------------------
  // Change tracking
  // ---------------------------------------------------------------------------

  const hasChanges = (() => {
    if (!initialFormRef.current) return false;
    const init = initialFormRef.current;
    return (
      formData.displayName !== init.displayName ||
      formData.description !== init.description ||
      formData.skillType !== init.skillType ||
      formData.instructionMarkdown !== init.instructionMarkdown ||
      formData.slashCommand !== init.slashCommand ||
      formData.category !== init.category ||
      formData.status !== init.status ||
      JSON.stringify(formData.tags) !== JSON.stringify(init.tags)
    );
  })();

  // ---------------------------------------------------------------------------
  // Field update + validation
  // ---------------------------------------------------------------------------

  const updateField = useCallback(
    (field: keyof SkillFormValues, value: unknown) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setSaveError(null);
    },
    []
  );

  const validateOnBlur = useCallback(
    (field: keyof SkillFormValues, value: unknown) => {
      const err = validateField(skillFormSchema, field, value);
      setFieldErrors((prev) => ({ ...prev, [field]: err }));
    },
    []
  );

  // ---------------------------------------------------------------------------
  // Save
  // ---------------------------------------------------------------------------

  const handleSave = useCallback(async () => {
    if (!entry) return;

    // Validate all fields
    const result = skillFormSchema.safeParse(formData);
    if (!result.success) {
      const errs: Record<string, string | null> = {};
      for (const issue of result.error.issues) {
        const key = issue.path[0];
        if (typeof key === "string") {
          errs[key] = issue.message;
        }
      }
      setFieldErrors(errs);
      return;
    }

    setSaving(true);
    setSaveError(null);

    // Build config update — merge with existing config
    const configUpdate: Record<string, unknown> = {
      ...entry.config,
      skill_type: formData.skillType,
      instruction_markdown: formData.instructionMarkdown,
      slash_command: formData.slashCommand,
      category: formData.category,
      tags: formData.tags,
    };

    // Parse allowed_tools from comma-separated string
    const parsedAllowedTools = allowedToolsStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    configUpdate.allowed_tools =
      parsedAllowedTools.length > 0 ? parsedAllowedTools : null;

    // Parse procedure_json if applicable
    if (formData.skillType === "procedural" && procedureJsonStr.trim()) {
      try {
        configUpdate.procedure_json = JSON.parse(procedureJsonStr);
      } catch {
        setFieldErrors((prev) => ({
          ...prev,
          procedureJson: "Invalid JSON",
        }));
        setSaving(false);
        return;
      }
    }

    const payload = {
      display_name: formData.displayName,
      description: formData.description,
      config: configUpdate,
      status: formData.status,
    };

    try {
      const res = await fetch(`/api/registry/${entry.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as Record<
          string,
          unknown
        > | null;
        throw new Error(
          (body?.detail as string) ?? `Save failed (HTTP ${res.status})`
        );
      }
      const raw = (await res.json()) as unknown;
      const updated = mapSnakeToCamel<RegistryEntry>(
        raw as Record<string, unknown>
      );
      setEntry(updated);
      initFormFromEntry(updated);
      setFieldErrors({});
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [entry, formData, allowedToolsStr, procedureJsonStr, initFormFromEntry]);

  // ---------------------------------------------------------------------------
  // Discard
  // ---------------------------------------------------------------------------

  const handleDiscard = useCallback(() => {
    if (entry) {
      initFormFromEntry(entry);
      setFieldErrors({});
      setSaveError(null);
      setPreviewMd(false);
    }
  }, [entry, initFormFromEntry]);

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  if (loading) {
    return <div className="text-gray-400 text-sm py-8">Loading skill...</div>;
  }

  if (error || !entry) {
    return (
      <div className="py-8">
        <p className="text-red-600 text-sm mb-4">
          {error ?? "Skill not found"}
        </p>
        <a
          href="/admin/skills"
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Skills
        </a>
      </div>
    );
  }

  const config = entry.config;
  const securityScore = config.security_score as number | null | undefined;
  const securityReport = config.security_report as
    | SecurityReport
    | null
    | undefined;

  const recommendationColor =
    securityReport?.recommendation === "approve"
      ? "bg-green-100 text-green-800"
      : securityReport?.recommendation === "review"
        ? "bg-yellow-100 text-yellow-800"
        : "bg-red-100 text-red-800";

  return (
    <RegistryDetailLayout
      entry={entry}
      backHref="/admin/skills"
      backLabel="Skills"
      tabs={TABS}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      hasChanges={hasChanges}
      saving={saving}
      onSave={handleSave}
      onDiscard={handleDiscard}
    >
      {saveError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {saveError}
        </div>
      )}

      {/* Overview tab */}
      {activeTab === "overview" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
          {/* Read-only fields */}
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">ID</dt>
              <dd className="font-mono text-gray-900 text-xs mt-0.5">
                {entry.id}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Name</dt>
              <dd className="text-gray-900 mt-0.5">{entry.name}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Skill Type</dt>
              <dd className="mt-0.5">
                <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
                  {(config.skill_type as string) ?? "instructional"}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Source Type</dt>
              <dd className="text-gray-900 mt-0.5">
                {(config.source_type as string) ?? "\u2014"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Slash Command</dt>
              <dd className="font-mono text-gray-900 text-xs mt-0.5">
                {(config.slash_command as string) ?? "\u2014"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Category</dt>
              <dd className="text-gray-900 mt-0.5">
                {(config.category as string) ?? "\u2014"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Tags</dt>
              <dd className="text-gray-900 mt-0.5">
                {(config.tags as string[] | null)?.join(", ") ?? "\u2014"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Security Score</dt>
              <dd className="text-gray-900 mt-0.5">
                {securityScore != null ? `${securityScore}/100` : "\u2014"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Owner</dt>
              <dd className="font-mono text-gray-900 text-xs mt-0.5">
                {entry.ownerId ?? "\u2014"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Created</dt>
              <dd className="text-gray-900 mt-0.5">
                {new Date(entry.createdAt).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Updated</dt>
              <dd className="text-gray-900 mt-0.5">
                {new Date(entry.updatedAt).toLocaleString()}
              </dd>
            </div>
          </dl>

          <hr className="border-gray-100" />

          {/* Editable fields */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={formData.displayName ?? ""}
                onChange={(e) =>
                  updateField("displayName", e.target.value || null)
                }
                onBlur={(e) =>
                  validateOnBlur("displayName", e.target.value || null)
                }
                placeholder="Optional display name"
                className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              {fieldErrors.displayName && (
                <p className="text-xs text-red-600 mt-1">
                  {fieldErrors.displayName}
                </p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={formData.description ?? ""}
                onChange={(e) =>
                  updateField("description", e.target.value || null)
                }
                onBlur={(e) =>
                  validateOnBlur("description", e.target.value || null)
                }
                placeholder="Optional description"
                rows={3}
                className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              {fieldErrors.description && (
                <p className="text-xs text-red-600 mt-1">
                  {fieldErrors.description}
                </p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
                value={formData.status}
                onChange={(e) =>
                  updateField(
                    "status",
                    e.target.value as SkillFormValues["status"]
                  )
                }
                className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="active">Active</option>
                <option value="disabled">Disabled</option>
                <option value="deprecated">Deprecated</option>
                <option value="draft">Draft</option>
                <option value="pending_review">Pending Review</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Config tab */}
      {activeTab === "config" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
          {/* Skill Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Skill Type
            </label>
            <select
              value={formData.skillType}
              onChange={(e) =>
                updateField(
                  "skillType",
                  e.target.value as SkillFormValues["skillType"]
                )
              }
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="instructional">Instructional</option>
              <option value="procedural">Procedural</option>
            </select>
          </div>

          {/* Instruction Markdown — visible for instructional */}
          {formData.skillType === "instructional" && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-sm font-medium text-gray-700">
                  Instruction Markdown
                </label>
                <button
                  onClick={() => setPreviewMd((p) => !p)}
                  className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                    previewMd
                      ? "bg-blue-50 border-blue-300 text-blue-700"
                      : "bg-white border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {previewMd ? "Edit" : "Preview"}
                </button>
              </div>
              {previewMd ? (
                <div className="prose prose-sm max-w-none p-3 border border-gray-200 rounded-md bg-gray-50 min-h-[12rem]">
                  <ReactMarkdown>
                    {formData.instructionMarkdown ?? ""}
                  </ReactMarkdown>
                </div>
              ) : (
                <textarea
                  value={formData.instructionMarkdown ?? ""}
                  onChange={(e) =>
                    updateField(
                      "instructionMarkdown",
                      e.target.value || null
                    )
                  }
                  onBlur={(e) =>
                    validateOnBlur(
                      "instructionMarkdown",
                      e.target.value || null
                    )
                  }
                  placeholder="Markdown instructions for this skill..."
                  rows={8}
                  className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              )}
              {fieldErrors.instructionMarkdown && (
                <p className="text-xs text-red-600 mt-1">
                  {fieldErrors.instructionMarkdown}
                </p>
              )}
            </div>
          )}

          {/* Procedure JSON — visible for procedural */}
          {formData.skillType === "procedural" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Procedure JSON
              </label>
              <textarea
                value={procedureJsonStr}
                onChange={(e) => {
                  setProcedureJsonStr(e.target.value);
                  setFieldErrors((prev) => ({
                    ...prev,
                    procedureJson: null,
                  }));
                }}
                placeholder='{"steps": [...]}'
                rows={8}
                className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              {fieldErrors.procedureJson && (
                <p className="text-xs text-red-600 mt-1">
                  {fieldErrors.procedureJson}
                </p>
              )}
            </div>
          )}

          {/* Slash Command */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Slash Command
            </label>
            <input
              type="text"
              value={formData.slashCommand ?? ""}
              onChange={(e) =>
                updateField("slashCommand", e.target.value || null)
              }
              onBlur={(e) =>
                validateOnBlur("slashCommand", e.target.value || null)
              }
              placeholder="/my-skill"
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            {fieldErrors.slashCommand && (
              <p className="text-xs text-red-600 mt-1">
                {fieldErrors.slashCommand}
              </p>
            )}
          </div>

          {/* Category */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Category
            </label>
            <input
              type="text"
              value={formData.category ?? ""}
              onChange={(e) =>
                updateField("category", e.target.value || null)
              }
              onBlur={(e) =>
                validateOnBlur("category", e.target.value || null)
              }
              placeholder="e.g. productivity, security"
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            {fieldErrors.category && (
              <p className="text-xs text-red-600 mt-1">
                {fieldErrors.category}
              </p>
            )}
          </div>

          {/* Tags */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tags
              <span className="text-xs text-gray-400 ml-1">
                (comma-separated)
              </span>
            </label>
            <input
              type="text"
              value={tagsStr}
              onChange={(e) => {
                setTagsStr(e.target.value);
                const parsed = e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean);
                updateField("tags", parsed.length > 0 ? parsed : null);
              }}
              placeholder="tag1, tag2, tag3"
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Allowed Tools */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Allowed Tools
              <span className="text-xs text-gray-400 ml-1">
                (comma-separated)
              </span>
            </label>
            <input
              type="text"
              value={allowedToolsStr}
              onChange={(e) => setAllowedToolsStr(e.target.value)}
              placeholder="email.send, calendar.read"
              className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Advanced (raw JSON) */}
          <details
            open={showAdvanced}
            onToggle={(e) =>
              setShowAdvanced(
                (e.target as HTMLDetailsElement).open
              )
            }
          >
            <summary className="cursor-pointer text-sm font-medium text-gray-500 select-none hover:text-gray-700">
              Advanced (raw JSON)
            </summary>
            <pre className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-xs overflow-auto max-h-64 text-gray-700">
              {JSON.stringify(config, null, 2)}
            </pre>
          </details>
        </div>
      )}

      {/* Scan Results tab */}
      {activeTab === "scan-results" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          {securityReport == null ? (
            <p className="text-sm text-gray-500">
              No scan results available. Use the admin Re-scan button to
              generate.
            </p>
          ) : (
            <div>
              {/* Score + recommendation */}
              <div className="flex items-center gap-4 mb-6">
                <div>
                  <span className="text-4xl font-bold text-gray-900">
                    {securityScore ?? "\u2014"}
                  </span>
                  <span className="text-gray-400 ml-1">/ 100</span>
                </div>
                {securityReport.recommendation && (
                  <span
                    className={`px-2 py-1 rounded text-sm font-medium ${recommendationColor}`}
                  >
                    {securityReport.recommendation.toUpperCase()}
                  </span>
                )}
                {securityReport.scan_engine && (
                  <span className="text-xs text-gray-400">
                    via {securityReport.scan_engine}
                  </span>
                )}
              </div>

              {/* Bandit issues */}
              <details className="mb-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-700 select-none">
                  Bandit Issues (
                  {securityReport.bandit_issues?.length ?? 0})
                </summary>
                <pre className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-xs overflow-auto max-h-64 text-gray-700">
                  {JSON.stringify(
                    securityReport.bandit_issues ?? [],
                    null,
                    2
                  )}
                </pre>
              </details>

              {/* pip-audit issues */}
              <details className="mb-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-700 select-none">
                  pip-audit Issues (
                  {securityReport.pip_audit_issues?.length ?? 0})
                </summary>
                <pre className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-xs overflow-auto max-h-64 text-gray-700">
                  {JSON.stringify(
                    securityReport.pip_audit_issues ?? [],
                    null,
                    2
                  )}
                </pre>
              </details>

              {/* Findings summary */}
              {securityReport.findings &&
                securityReport.findings.length > 0 && (
                  <details className="mb-4">
                    <summary className="cursor-pointer text-sm font-medium text-gray-700 select-none">
                      All Findings ({securityReport.findings.length})
                    </summary>
                    <pre className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-xs overflow-auto max-h-64 text-gray-700">
                      {JSON.stringify(securityReport.findings, null, 2)}
                    </pre>
                  </details>
                )}
            </div>
          )}
        </div>
      )}
    </RegistryDetailLayout>
  );
}
