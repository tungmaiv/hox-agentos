/**
 * TypeScript types for admin API responses.
 *
 * These interfaces mirror the backend Pydantic response schemas in
 * backend/core/schemas/registry.py. Field names use camelCase for
 * frontend convention; the API returns snake_case which is mapped
 * in the hooks layer.
 */

// ---------------------------------------------------------------------------
// Artifact types
// ---------------------------------------------------------------------------

export type ArtifactType = "agents" | "tools" | "skills" | "mcp-servers";
export type ViewMode = "table" | "cards";
export type ArtifactStatus = "active" | "disabled" | "deprecated" | "pending_review";

// ---------------------------------------------------------------------------
// Agent definitions
// ---------------------------------------------------------------------------

export interface AgentDefinition {
  id: string;
  name: string;
  displayName: string | null;
  description: string | null;
  version: string;
  isActive: boolean;
  status: ArtifactStatus;
  lastSeenAt: string | null;
  handlerModule: string | null;
  handlerFunction: string | null;
  routingKeywords: string[] | null;
  configJson: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface AgentDefinitionCreate {
  name: string;
  display_name?: string | null;
  description?: string | null;
  version?: string;
  handler_module?: string | null;
  handler_function?: string | null;
  routing_keywords?: string[] | null;
  config_json?: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

export interface ToolDefinition {
  id: string;
  name: string;
  displayName: string | null;
  description: string | null;
  version: string;
  isActive: boolean;
  status: ArtifactStatus;
  lastSeenAt: string | null;
  handlerType: string;
  handlerModule: string | null;
  handlerFunction: string | null;
  mcpServerId: string | null;
  mcpToolName: string | null;
  sandboxRequired: boolean;
  inputSchema: Record<string, unknown> | null;
  outputSchema: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface ToolDefinitionCreate {
  name: string;
  display_name?: string | null;
  description?: string | null;
  version?: string;
  handler_type?: "backend" | "mcp" | "sandbox";
  handler_module?: string | null;
  handler_function?: string | null;
  mcp_server_id?: string | null;
  mcp_tool_name?: string | null;
  sandbox_required?: boolean;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Skill definitions
// ---------------------------------------------------------------------------

export interface SkillDefinition {
  id: string;
  name: string;
  displayName: string | null;
  description: string | null;
  version: string;
  isActive: boolean;
  status: ArtifactStatus;
  lastSeenAt: string | null;
  skillType: string;
  slashCommand: string | null;
  sourceType: string;
  instructionMarkdown: string | null;
  procedureJson: Record<string, unknown> | null;
  inputSchema: Record<string, unknown> | null;
  outputSchema: Record<string, unknown> | null;
  // agentskills.io standard fields
  license: string | null;
  compatibility: string | null;
  metadataJson: Record<string, unknown> | null;
  allowedTools: string[] | null;
  tags: string[] | null;
  category: string | null;
  sourceUrl: string | null;
  securityScore: number | null;
  securityReport: Record<string, unknown> | null;
  reviewedBy: string | null;
  reviewedAt: string | null;
  usageCount: number;
  isPromoted: boolean;
  createdBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SkillShareEntry {
  user_id: string;
  created_at: string;
}

export interface SkillDefinitionCreate {
  name: string;
  display_name?: string | null;
  description?: string | null;
  version?: string;
  skill_type: "instructional" | "procedural";
  slash_command?: string | null;
  source_type?: "builtin" | "imported" | "user_created";
  instruction_markdown?: string | null;
  procedure_json?: Record<string, unknown> | null;
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// MCP servers
// ---------------------------------------------------------------------------

export interface McpServerEntry {
  id: string;
  name: string;
  displayName: string | null;
  url: string;
  version: string | null;
  isActive: boolean;
  status: ArtifactStatus;
  lastSeenAt: string | null;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// Permissions
// ---------------------------------------------------------------------------

export interface ArtifactPermission {
  id: string;
  artifactType: string;
  artifactId: string;
  role: string;
  allowed: boolean;
  status: string;
  createdAt: string;
}

export interface UserArtifactPermission {
  id: string;
  artifactType: string;
  artifactId: string;
  userId: string;
  allowed: boolean;
  status: string;
  createdAt: string;
}

export interface RolePermissions {
  [role: string]: string[];
}

export interface ArtifactPermissionSetEntry {
  role: string;
  allowed: boolean;
}

export interface UserPermissionSetEntry {
  artifact_type: string;
  user_id: string;
  allowed: boolean;
}

// ---------------------------------------------------------------------------
// Generic artifact (union for table/card components)
// ---------------------------------------------------------------------------

export interface ArtifactBase {
  id: string;
  name: string;
  displayName: string | null;
  description: string | null;
  version: string;
  isActive: boolean;
  status: ArtifactStatus;
  lastSeenAt: string | null;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// Utility: snake_case to camelCase mapper
// ---------------------------------------------------------------------------

/** Convert a snake_case key to camelCase. */
function snakeToCamel(key: string): string {
  return key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}

/** Map all keys in an object from snake_case to camelCase (shallow). */
export function mapSnakeToCamel<T>(obj: Record<string, unknown>): T {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    result[snakeToCamel(key)] = value;
  }
  return result as T;
}

/** Map an array of objects from snake_case to camelCase. */
export function mapArraySnakeToCamel<T>(arr: unknown[]): T[] {
  return arr.map((item) => mapSnakeToCamel<T>(item as Record<string, unknown>));
}
