"use client";
/**
 * ArtifactWizardForm — structured form panel for the artifact creation wizard.
 *
 * Manages artifact type selection, template/clone shortcuts, common fields
 * (name with live availability check, description, version), type-specific
 * fields, a JSON preview panel, and Cancel/Submit actions.
 *
 * Exports FormState for use by ArtifactWizardTemplates.
 */
import { useEffect, useState } from "react";
import { ArtifactWizardNameCheck } from "./artifact-wizard-name-check";
import { ArtifactWizardTemplates } from "./artifact-wizard-templates";
import { CloneArtifactModal } from "./clone-artifact-modal";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FormState {
  name: string;
  description: string;
  version: string;
  // Agent fields
  model_alias: string;
  system_prompt: string;
  // Tool + Skill fields
  required_permissions: string[];
  sandbox_required: boolean;
  handler_module: string;  // Tool
  entry_point: string;     // Skill
  // MCP Server fields
  url: string;
  auth_token: string;
}

export const EMPTY_FORM: FormState = {
  name: "",
  description: "",
  version: "1.0.0",
  model_alias: "blitz/master",
  system_prompt: "",
  required_permissions: [],
  sandbox_required: false,
  handler_module: "",
  entry_point: "",
  url: "",
  auth_token: "",
};

interface ArtifactWizardFormProps {
  formState: FormState;
  artifactType: string | null;
  /** Field names to pulse with blue highlight (from AI fill_form calls). */
  aiFilledFields: Set<string>;
  onFormChange: (updates: Partial<FormState>) => void;
  onArtifactTypeChange: (type: string) => void;
  /** Called when Cancel is clicked — parent resets form state. */
  onCancel: () => void;
  /** Called when Submit is clicked — parent handles POST. */
  onSubmit: () => void;
  isSubmitting: boolean;
}

// ---------------------------------------------------------------------------
// Hardcoded permission strings
// ---------------------------------------------------------------------------

const KNOWN_PERMISSIONS = [
  "tool:email",
  "tool:calendar",
  "tool:project",
  "tool:crm",
  "mcp:read",
  "mcp:write",
  "registry:read",
  "registry:manage",
  "memory:read",
  "memory:write",
  "admin:read",
  "admin:write",
];

const MODEL_ALIASES = ["blitz/master", "blitz/fast", "blitz/coder", "blitz/summarizer"];

const ARTIFACT_TYPES = [
  { value: "agent", label: "Agent" },
  { value: "tool", label: "Tool" },
  { value: "skill", label: "Skill" },
  { value: "mcp_server", label: "MCP Server" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildSubmitPayload(
  formState: FormState,
  artifactType: string | null
): Record<string, unknown> {
  const base: Record<string, unknown> = {
    name: formState.name,
    description: formState.description || undefined,
    version: formState.version || "1.0.0",
  };

  switch (artifactType) {
    case "agent":
      return {
        ...base,
        config_json: {
          model_alias: formState.model_alias || undefined,
          system_prompt: formState.system_prompt || undefined,
        },
      };
    case "tool":
      return {
        ...base,
        handler_module: formState.handler_module || undefined,
        sandbox_required: formState.sandbox_required,
        required_permissions: formState.required_permissions,
      };
    case "skill":
      return {
        ...base,
        skill_type: "instructional",
        source_type: "user_created",
        entry_point: formState.entry_point || undefined,
        required_permissions: formState.required_permissions,
        sandbox_required: formState.sandbox_required,
      };
    case "mcp_server":
      return {
        ...base,
        url: formState.url,
        auth_token: formState.auth_token || undefined,
      };
    default:
      return base;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
      {children}
    </h3>
  );
}

function FieldWrapper({
  label,
  children,
  highlight,
}: {
  label: string;
  children: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={`mb-3 rounded-md transition-colors duration-700 ${
        highlight ? "animate-pulse bg-blue-50 p-1 -m-1" : ""
      }`}
    >
      <label className="block text-xs font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

function PermissionsChecklist({
  selected,
  onChange,
  highlight,
}: {
  selected: string[];
  onChange: (perms: string[]) => void;
  highlight?: boolean;
}) {
  const toggle = (perm: string) => {
    if (selected.includes(perm)) {
      onChange(selected.filter((p) => p !== perm));
    } else {
      onChange([...selected, perm]);
    }
  };

  return (
    <div
      className={`grid grid-cols-2 gap-x-3 gap-y-1 p-2 border border-gray-200 rounded-md bg-white ${
        highlight ? "bg-blue-50" : ""
      }`}
    >
      {KNOWN_PERMISSIONS.map((perm) => (
        <label key={perm} className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={selected.includes(perm)}
            onChange={() => toggle(perm)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-700 font-mono">{perm}</span>
        </label>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ArtifactWizardForm({
  formState,
  artifactType,
  aiFilledFields,
  onFormChange,
  onArtifactTypeChange,
  onCancel,
  onSubmit,
  isSubmitting,
}: ArtifactWizardFormProps) {
  const [nameAvailable, setNameAvailable] = useState<boolean | null>(null);
  const [nameTouched, setNameTouched] = useState(false);
  const [showCloneModal, setShowCloneModal] = useState(false);
  // Track which fields are currently pulsing
  const [pulsingFields, setPulsingFields] = useState<Set<string>>(new Set());

  // Trigger pulse animation when aiFilledFields changes
  useEffect(() => {
    if (aiFilledFields.size === 0) return;
    setPulsingFields(new Set(aiFilledFields));
    const timer = setTimeout(() => {
      setPulsingFields(new Set());
    }, 1500);
    return () => clearTimeout(timer);
  }, [aiFilledFields]);

  const isSubmitDisabled =
    isSubmitting ||
    !formState.name ||
    nameAvailable !== true ||
    !artifactType;

  const inputCls =
    "w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4 space-y-5">

        {/* Section 1: Artifact Type */}
        <div>
          <SectionLabel>Artifact Type</SectionLabel>
          <div className="flex flex-wrap gap-2">
            {ARTIFACT_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => {
                  onArtifactTypeChange(t.value);
                  // Reset name availability when type changes
                  setNameAvailable(null);
                  setNameTouched(false);
                }}
                className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                  artifactType === t.value
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-700 border-gray-300 hover:border-blue-400 hover:bg-blue-50"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Section 2: Template / Clone */}
        {artifactType && (
          <div>
            <SectionLabel>Start From</SectionLabel>
            <div className="flex gap-2 flex-wrap">
              <button
                type="button"
                onClick={onCancel}
                className="px-3 py-1.5 text-xs border border-gray-200 rounded-md hover:bg-gray-50 text-gray-600"
              >
                Start Blank
              </button>
              <button
                type="button"
                onClick={() => setShowCloneModal(true)}
                className="px-3 py-1.5 text-xs border border-gray-200 rounded-md hover:bg-gray-50 text-gray-600"
              >
                Clone Existing
              </button>
            </div>
            <ArtifactWizardTemplates
              artifactType={artifactType}
              onSelect={(defaults) => {
                onFormChange(defaults);
                if (defaults.name) {
                  setNameTouched(false);
                  setNameAvailable(null);
                }
              }}
            />
          </div>
        )}

        {/* Section 3: Common Fields */}
        <div>
          <SectionLabel>Basic Info</SectionLabel>
          <FieldWrapper label="Name *" highlight={pulsingFields.has("name") || pulsingFields.has("form_name")}>
            <ArtifactWizardNameCheck
              artifactType={artifactType}
              value={formState.name}
              onChange={(v) => {
                onFormChange({ name: v });
                setNameTouched(true);
              }}
              onAvailabilityChange={setNameAvailable}
              onBlur={() => setNameTouched(true)}
            />
            {nameTouched && nameAvailable === false && (
              <p className="text-xs text-red-600 mt-1">
                This name is already taken. Please choose a different name.
              </p>
            )}
          </FieldWrapper>

          <FieldWrapper label="Description" highlight={pulsingFields.has("description") || pulsingFields.has("form_description")}>
            <textarea
              value={formState.description}
              onChange={(e) => onFormChange({ description: e.target.value })}
              rows={2}
              className={inputCls}
              placeholder="Brief description of what this artifact does"
            />
          </FieldWrapper>

          <FieldWrapper label="Version" highlight={pulsingFields.has("version") || pulsingFields.has("form_version")}>
            <input
              type="text"
              value={formState.version}
              onChange={(e) => onFormChange({ version: e.target.value })}
              className={inputCls}
              placeholder="1.0.0"
            />
          </FieldWrapper>
        </div>

        {/* Section 4: Type-specific Fields */}
        {artifactType === "agent" && (
          <div>
            <SectionLabel>Agent Settings</SectionLabel>
            <FieldWrapper label="Model Alias" highlight={pulsingFields.has("model_alias") || pulsingFields.has("form_model_alias")}>
              <select
                value={formState.model_alias}
                onChange={(e) => onFormChange({ model_alias: e.target.value })}
                className={inputCls}
              >
                {MODEL_ALIASES.map((alias) => (
                  <option key={alias} value={alias}>
                    {alias}
                  </option>
                ))}
              </select>
            </FieldWrapper>
            <FieldWrapper label="System Prompt" highlight={pulsingFields.has("system_prompt") || pulsingFields.has("form_system_prompt")}>
              <textarea
                value={formState.system_prompt}
                onChange={(e) => onFormChange({ system_prompt: e.target.value })}
                rows={4}
                className={inputCls}
                placeholder="You are an agent that..."
              />
            </FieldWrapper>
          </div>
        )}

        {artifactType === "tool" && (
          <div>
            <SectionLabel>Tool Settings</SectionLabel>
            <FieldWrapper label="Handler Module" highlight={pulsingFields.has("handler_module") || pulsingFields.has("form_handler_module")}>
              <input
                type="text"
                value={formState.handler_module}
                onChange={(e) => onFormChange({ handler_module: e.target.value })}
                className={inputCls}
                placeholder="tools.my_tool"
              />
            </FieldWrapper>
            <FieldWrapper label="Required Permissions" highlight={pulsingFields.has("required_permissions") || pulsingFields.has("form_required_permissions")}>
              <PermissionsChecklist
                selected={formState.required_permissions}
                onChange={(perms) => onFormChange({ required_permissions: perms })}
              />
            </FieldWrapper>
            <FieldWrapper label="" highlight={pulsingFields.has("sandbox_required") || pulsingFields.has("form_sandbox_required")}>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formState.sandbox_required}
                  onChange={(e) => onFormChange({ sandbox_required: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600"
                />
                <span className="text-sm text-gray-700">Sandbox Required (Docker)</span>
              </label>
            </FieldWrapper>
          </div>
        )}

        {artifactType === "skill" && (
          <div>
            <SectionLabel>Skill Settings</SectionLabel>
            <FieldWrapper label="Entry Point" highlight={pulsingFields.has("entry_point") || pulsingFields.has("form_entry_point")}>
              <input
                type="text"
                value={formState.entry_point}
                onChange={(e) => onFormChange({ entry_point: e.target.value })}
                className={inputCls}
                placeholder="skills.my_skill:run"
              />
            </FieldWrapper>
            <FieldWrapper label="Required Permissions" highlight={pulsingFields.has("required_permissions") || pulsingFields.has("form_required_permissions")}>
              <PermissionsChecklist
                selected={formState.required_permissions}
                onChange={(perms) => onFormChange({ required_permissions: perms })}
              />
            </FieldWrapper>
            <FieldWrapper label="" highlight={pulsingFields.has("sandbox_required") || pulsingFields.has("form_sandbox_required")}>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formState.sandbox_required}
                  onChange={(e) => onFormChange({ sandbox_required: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600"
                />
                <span className="text-sm text-gray-700">Sandbox Required (Docker)</span>
              </label>
            </FieldWrapper>
          </div>
        )}

        {artifactType === "mcp_server" && (
          <div>
            <SectionLabel>MCP Server Settings</SectionLabel>
            <FieldWrapper label="Server URL *" highlight={pulsingFields.has("url") || pulsingFields.has("form_url")}>
              <input
                type="url"
                value={formState.url}
                onChange={(e) => onFormChange({ url: e.target.value })}
                className={inputCls}
                placeholder="http://my-mcp-server:8001"
              />
            </FieldWrapper>
            <FieldWrapper label="Auth Token (optional)">
              <input
                type="password"
                value={formState.auth_token}
                onChange={(e) => onFormChange({ auth_token: e.target.value })}
                className={inputCls}
                placeholder="Leave blank if no auth required"
              />
            </FieldWrapper>
          </div>
        )}

        {/* Section 5: JSON Preview */}
        {artifactType && (
          <div>
            <SectionLabel>JSON Preview</SectionLabel>
            <pre className="bg-gray-50 border border-gray-200 rounded-md p-3 text-xs font-mono overflow-auto max-h-48 text-gray-700">
              {JSON.stringify(buildSubmitPayload(formState, artifactType), null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Section 6: Actions */}
      <div className="flex-shrink-0 px-4 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={isSubmitDisabled}
          className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
        >
          {isSubmitting ? "Creating..." : "Create Artifact"}
        </button>
      </div>

      {/* Clone Modal */}
      {showCloneModal && artifactType && (
        <CloneArtifactModal
          artifactType={artifactType}
          onSelect={(artifact) => {
            onFormChange({
              name: `${artifact.name}_copy`,
              description: (artifact.description as string | undefined) ?? "",
            });
            setNameTouched(false);
            setNameAvailable(null);
            setShowCloneModal(false);
          }}
          onClose={() => setShowCloneModal(false)}
        />
      )}
    </div>
  );
}
