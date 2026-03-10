"use client";
/**
 * ArtifactWizard — top-level shell for the hybrid artifact creation wizard.
 *
 * Split-panel layout:
 * - Left (45%): structured form with type selector, templates, fields, JSON preview
 * - Right (55%): CopilotKit AI chat assistant with fill_form co-agent tool
 *
 * Bidirectional state sync:
 * - AI → Form: useCoAgentStateRender watches artifact_builder state for form_* fields
 *              and merges them into formState + tracks which fields changed for pulse animation
 * - Form → AI: CopilotKit passes form context via initial messages
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { useCoAgentStateRender } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import { toast } from "sonner";

import { ArtifactWizardForm, type FormState, EMPTY_FORM } from "./artifact-wizard-form";

/** Map artifact_type to admin API path segment */
const TYPE_TO_PATH: Record<string, string> = {
  agent: "agents",
  tool: "tools",
  skill: "skills",
  mcp_server: "mcp-servers",
};

/** Map artifact_type to display label for success toast */
const TYPE_TO_LABEL: Record<string, string> = {
  agent: "Agent",
  tool: "Tool",
  skill: "Skill",
  mcp_server: "MCP Server",
};

/** Co-agent state shape emitted by artifact_builder backend */
interface BuilderCoAgentState {
  artifact_type?: string | null;
  artifact_draft?: Record<string, unknown> | null;
  validation_errors?: string[];
  is_complete?: boolean;
  // Form field values from fill_form tool
  form_name?: string | null;
  form_description?: string | null;
  form_version?: string | null;
  form_required_permissions?: string[] | null;
  form_model_alias?: string | null;
  form_system_prompt?: string | null;
  form_handler_module?: string | null;
  form_sandbox_required?: boolean | null;
  form_entry_point?: string | null;
  form_url?: string | null;
  form_instruction_markdown?: string | null;
  handler_code?: string | null;
}

function WizardInner() {
  const searchParams = useSearchParams();
  const cloneType = searchParams.get("clone_type");
  const cloneId = searchParams.get("clone_id");

  const [formState, setFormState] = useState<FormState>(EMPTY_FORM);
  const [artifactType, setArtifactType] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [aiFilledFields, setAiFilledFields] = useState<Set<string>>(new Set());
  const [cloneSourceName, setCloneSourceName] = useState<string | null>(null);
  const [aiHandlerCode, setAiHandlerCode] = useState<string | null>(null);

  // Ref to buffer co-agent state updates — avoids setState during render phase
  const pendingStateRef = useRef<BuilderCoAgentState | null>(null);

  // Subscribe to artifact_builder co-agent state for live form updates
  useCoAgentStateRender<BuilderCoAgentState>({
    name: "artifact_builder",
    render: ({ state }) => {
      if (state) {
        pendingStateRef.current = state;
      }
      return null;
    },
  });

  // Apply buffered state outside render phase — merge form_* fields
  useEffect(() => {
    const id = setInterval(() => {
      const pending = pendingStateRef.current;
      if (!pending) return;
      pendingStateRef.current = null;

      const changedFields = new Set<string>();
      const updates: Partial<FormState> = {};

      if (pending.form_name != null && pending.form_name !== formState.name) {
        updates.name = pending.form_name;
        changedFields.add("name");
      }
      if (pending.form_description != null && pending.form_description !== formState.description) {
        updates.description = pending.form_description;
        changedFields.add("description");
      }
      if (pending.form_version != null && pending.form_version !== formState.version) {
        updates.version = pending.form_version;
        changedFields.add("version");
      }
      if (pending.form_model_alias != null && pending.form_model_alias !== formState.model_alias) {
        updates.model_alias = pending.form_model_alias;
        changedFields.add("model_alias");
      }
      if (pending.form_system_prompt != null && pending.form_system_prompt !== formState.system_prompt) {
        updates.system_prompt = pending.form_system_prompt;
        changedFields.add("system_prompt");
      }
      if (pending.form_handler_module != null && pending.form_handler_module !== formState.handler_module) {
        updates.handler_module = pending.form_handler_module;
        changedFields.add("handler_module");
      }
      if (pending.form_entry_point != null && pending.form_entry_point !== formState.entry_point) {
        updates.entry_point = pending.form_entry_point;
        changedFields.add("entry_point");
      }
      if (pending.form_url != null && pending.form_url !== formState.url) {
        updates.url = pending.form_url;
        changedFields.add("url");
      }
      if (
        pending.form_required_permissions != null &&
        JSON.stringify(pending.form_required_permissions) !==
          JSON.stringify(formState.required_permissions)
      ) {
        updates.required_permissions = pending.form_required_permissions;
        changedFields.add("required_permissions");
      }
      if (pending.form_sandbox_required != null && pending.form_sandbox_required !== formState.sandbox_required) {
        updates.sandbox_required = pending.form_sandbox_required;
        changedFields.add("sandbox_required");
      }
      if (pending.form_instruction_markdown != null && pending.form_instruction_markdown !== formState.instruction_markdown) {
        updates.instruction_markdown = pending.form_instruction_markdown;
        changedFields.add("instruction_markdown");
      }

      // Update artifact_type if AI set it
      if (pending.artifact_type && pending.artifact_type !== artifactType) {
        setArtifactType(pending.artifact_type);
      }
      // Capture generated handler stub for tool save payload
      if (pending.handler_code != null) {
        setAiHandlerCode(pending.handler_code);
      }

      if (Object.keys(updates).length > 0) {
        setFormState((prev) => ({ ...prev, ...updates }));
        setAiFilledFields(changedFields);
      }
    }, 100);
    return () => clearInterval(id);
  }, [formState, artifactType]);

  // Load clone source on mount if clone params present
  useEffect(() => {
    if (!cloneType || !cloneId) return;
    const path = TYPE_TO_PATH[cloneType];
    if (!path) return;

    fetch(`/api/admin/${path}/${cloneId}`)
      .then(async (res) => {
        if (!res.ok) return;
        const data = (await res.json()) as Record<string, unknown>;
        // Pre-fill form from clone source
        const clonedName = typeof data.name === "string" ? `${data.name}_copy` : "";
        setArtifactType(cloneType);
        setCloneSourceName(typeof data.name === "string" ? data.name : null);
        setFormState((prev) => ({
          ...prev,
          name: clonedName,
          description: typeof data.description === "string" ? data.description : "",
          version: typeof data.version === "string" ? data.version : "1.0.0",
          // Agent-specific
          model_alias:
            typeof (data.config_json as Record<string, unknown> | null)?.model_alias === "string"
              ? ((data.config_json as Record<string, unknown>).model_alias as string)
              : prev.model_alias,
          system_prompt:
            typeof (data.config_json as Record<string, unknown> | null)?.system_prompt === "string"
              ? ((data.config_json as Record<string, unknown>).system_prompt as string)
              : prev.system_prompt,
          // Tool/Skill-specific
          handler_module: typeof data.handler_module === "string" ? data.handler_module : prev.handler_module,
          entry_point: typeof data.entry_point === "string" ? data.entry_point : prev.entry_point,
          instruction_markdown: typeof data.instruction_markdown === "string" ? data.instruction_markdown : prev.instruction_markdown,
          sandbox_required: typeof data.sandbox_required === "boolean" ? data.sandbox_required : prev.sandbox_required,
          // MCP-specific
          url: typeof data.url === "string" ? data.url : prev.url,
        }));
      })
      .catch(() => {
        // Silently ignore — form stays blank
      });
  }, [cloneType, cloneId]);

  const handleFormChange = useCallback((updates: Partial<FormState>) => {
    setFormState((prev) => ({ ...prev, ...updates }));
  }, []);

  const handleArtifactTypeChange = useCallback((type: string) => {
    setArtifactType(type);
    // Reset type-specific fields when switching types
    setFormState((prev) => ({
      ...EMPTY_FORM,
      name: prev.name,
      description: prev.description,
      version: prev.version,
    }));
  }, []);

  const handleCancel = useCallback(() => {
    setFormState(EMPTY_FORM);
    setArtifactType(null);
    setAiFilledFields(new Set());
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!artifactType || !formState.name) return;

    const path = TYPE_TO_PATH[artifactType];
    if (!path) {
      toast.error("Unknown artifact type");
      return;
    }

    setIsSubmitting(true);

    // Build submission payload
    const payload: Record<string, unknown> = {
      name: formState.name,
      description: formState.description || undefined,
      version: formState.version || "1.0.0",
    };

    switch (artifactType) {
      case "agent":
        payload.config_json = {
          model_alias: formState.model_alias || undefined,
          system_prompt: formState.system_prompt || undefined,
        };
        break;
      case "tool":
        payload.handler_module = formState.handler_module || undefined;
        payload.sandbox_required = formState.sandbox_required;
        payload.required_permissions = formState.required_permissions;
        if (aiHandlerCode) payload.handler_code = aiHandlerCode;
        break;
      case "skill":
        payload.skill_type = "instructional";
        payload.source_type = "user_created";
        payload.instruction_markdown = formState.instruction_markdown || undefined;
        payload.entry_point = formState.entry_point || undefined;
        payload.required_permissions = formState.required_permissions;
        payload.sandbox_required = formState.sandbox_required;
        break;
      case "mcp_server":
        payload.url = formState.url;
        payload.auth_token = formState.auth_token || undefined;
        break;
    }

    try {
      const res = await fetch(`/api/admin/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
        let errorMsg = `HTTP ${res.status}`;
        if (typeof body.detail === "string") {
          errorMsg = body.detail;
        } else if (Array.isArray(body.detail)) {
          errorMsg = (body.detail as Array<Record<string, unknown>>)
            .map((e) => {
              const loc = Array.isArray(e.loc) ? (e.loc as string[]).join(" > ") : "";
              return loc ? `${loc}: ${e.msg}` : String(e.msg ?? e);
            })
            .join("; ");
        }
        throw new Error(errorMsg);
      }

      const label = TYPE_TO_LABEL[artifactType] ?? artifactType;
      const tabPath = path;
      toast.success(`${label} created — view in /${tabPath} tab`);

      // Reset form after success
      setFormState(EMPTY_FORM);
      setArtifactType(null);
      setAiFilledFields(new Set());
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to create artifact — try again"
      );
    } finally {
      setIsSubmitting(false);
    }
  }, [artifactType, formState]);

  // Chat initial message depends on mode (fresh vs clone)
  const chatInitial = cloneSourceName
    ? `I've pre-filled from "${cloneSourceName}". Change anything or tell me what to adjust.`
    : "I can create agents, tools, skills, and MCP servers. Just describe what you need.";

  return (
    <div className="flex gap-4 h-[calc(100vh-140px)]">
      {/* Left panel: Structured Form (45%) */}
      <div className="w-[45%] flex flex-col border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
          <h2 className="text-sm font-semibold text-gray-900">Create Artifact</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Fill in the form or let the AI assistant guide you
          </p>
        </div>
        <ArtifactWizardForm
          formState={formState}
          artifactType={artifactType}
          aiFilledFields={aiFilledFields}
          onFormChange={handleFormChange}
          onArtifactTypeChange={handleArtifactTypeChange}
          onCancel={handleCancel}
          onSubmit={handleSubmit}
          isSubmitting={isSubmitting}
        />
      </div>

      {/* Right panel: AI Chat Assistant (55%) */}
      <div className="w-[55%] flex flex-col border border-gray-200 rounded-lg overflow-hidden bg-white">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
          <h2 className="text-sm font-semibold text-gray-900">AI Assistant</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Describe what you need — AI will fill the form
          </p>
        </div>
        <div className="flex-1 overflow-hidden">
          <CopilotChat
            className="h-full"
            labels={{ initial: chatInitial }}
          />
        </div>
      </div>
    </div>
  );
}

export function ArtifactWizard() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="artifact_builder">
      <WizardInner />
    </CopilotKit>
  );
}
