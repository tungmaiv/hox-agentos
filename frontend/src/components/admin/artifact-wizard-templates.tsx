"use client";
/**
 * ArtifactWizardTemplates — hardcoded template cards per artifact type.
 *
 * Renders template selection buttons that pre-fill the form when clicked.
 * Templates are keyed by artifact_type ("agent", "tool", "skill", "mcp_server").
 */
import { type FormState } from "./artifact-wizard-form";

interface Template {
  id: string;
  label: string;
  description: string;
  defaults: Partial<FormState>;
}

const TEMPLATES: Record<string, Template[]> = {
  agent: [
    {
      id: "email-digest-agent",
      label: "Email Digest Agent",
      description: "Fetches and summarizes emails daily",
      defaults: {
        name: "email-digest-agent",
        description: "Fetches and summarizes inbox emails on a schedule.",
        version: "1.0.0",
        model_alias: "blitz/master",
        system_prompt:
          "You are an email assistant. Fetch the user's recent emails and summarize the most important ones.",
      },
    },
    {
      id: "project-status-agent",
      label: "Project Status Agent",
      description: "Reports project task status on demand",
      defaults: {
        name: "project-status-agent",
        description: "Summarizes project tasks and blockers.",
        version: "1.0.0",
        model_alias: "blitz/fast",
        system_prompt:
          "You are a project assistant. Report the current status of tasks and highlight blockers.",
      },
    },
  ],
  tool: [
    {
      id: "rest-api-tool",
      label: "REST API Tool",
      description: "Calls an external REST endpoint",
      defaults: {
        name: "rest-api-tool",
        description: "Makes HTTP requests to an external REST API.",
        version: "1.0.0",
        handler_module: "tools.rest_api",
      },
    },
    {
      id: "python-script-tool",
      label: "Python Script Tool",
      description: "Executes a sandboxed Python script",
      defaults: {
        name: "python-script-tool",
        description: "Runs a Python script in a Docker sandbox.",
        version: "1.0.0",
        sandbox_required: true,
        handler_module: "tools.python_script",
      },
    },
  ],
  skill: [
    {
      id: "summarizer-skill",
      label: "Summarizer Skill",
      description: "Summarizes any text input",
      defaults: {
        name: "summarizer-skill",
        description: "Summarizes long text into key points.",
        version: "1.0.0",
        entry_point: "skills.summarizer:run",
      },
    },
    {
      id: "data-extractor-skill",
      label: "Data Extractor Skill",
      description: "Extracts structured data from unstructured text",
      defaults: {
        name: "data-extractor-skill",
        description: "Extracts entities and facts from text.",
        version: "1.0.0",
        entry_point: "skills.data_extractor:run",
      },
    },
  ],
  mcp_server: [
    {
      id: "openapi-mcp-server",
      label: "OpenAPI MCP Server",
      description: "Exposes an OpenAPI service as MCP tools",
      defaults: {
        name: "openapi-mcp-server",
        description: "MCP server wrapping an OpenAPI-documented service.",
        version: "1.0.0",
        url: "http://localhost:8001",
      },
    },
  ],
};

interface Props {
  artifactType: string | null;
  onSelect: (defaults: Partial<FormState>) => void;
}

export function ArtifactWizardTemplates({ artifactType, onSelect }: Props) {
  const templates = artifactType ? (TEMPLATES[artifactType] ?? []) : [];
  if (templates.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {templates.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onSelect(t.defaults)}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg hover:border-blue-400 hover:bg-blue-50 text-left transition-colors"
        >
          <div className="font-medium text-gray-900">{t.label}</div>
          <div className="text-xs text-gray-500 mt-0.5">{t.description}</div>
        </button>
      ))}
    </div>
  );
}
