/**
 * Zod validation schemas for registry entry form editing.
 *
 * Each schema covers the editable fields for one registry type.
 * Used for on-blur field validation and pre-submit validation on detail pages.
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// Shared status enum
// ---------------------------------------------------------------------------

const registryStatusEnum = z.enum([
  "active",
  "disabled",
  "deprecated",
  "draft",
  "archived",
  "pending_review",
]);

// ---------------------------------------------------------------------------
// Agent form schema
// ---------------------------------------------------------------------------

export const agentFormSchema = z.object({
  displayName: z.string().optional().nullable(),
  description: z.string().optional().nullable(),
  systemPrompt: z.string().optional().nullable(),
  modelAlias: z
    .enum(["blitz/master", "blitz/fast", "blitz/coder", "blitz/summarizer"])
    .optional()
    .nullable(),
  routingKeywords: z.array(z.string()).optional().nullable(),
  status: registryStatusEnum,
});

export type AgentFormValues = z.infer<typeof agentFormSchema>;

// ---------------------------------------------------------------------------
// Tool form schema
// ---------------------------------------------------------------------------

export const toolFormSchema = z.object({
  displayName: z.string().optional().nullable(),
  description: z.string().optional().nullable(),
  handlerType: z.enum(["backend", "mcp", "sandbox"]),
  handlerModule: z.string().optional().nullable(),
  handlerFunction: z.string().optional().nullable(),
  mcpToolName: z.string().optional().nullable(),
  sandboxRequired: z.boolean(),
  status: registryStatusEnum,
});

export type ToolFormValues = z.infer<typeof toolFormSchema>;

// ---------------------------------------------------------------------------
// MCP Server form schema
// ---------------------------------------------------------------------------

export const mcpServerFormSchema = z.object({
  displayName: z.string().optional().nullable(),
  description: z.string().optional().nullable(),
  url: z.string().url("Must be a valid URL"),
  authToken: z.string().optional().nullable(),
  status: registryStatusEnum,
});

export type McpServerFormValues = z.infer<typeof mcpServerFormSchema>;

// ---------------------------------------------------------------------------
// Skill form schema
// ---------------------------------------------------------------------------

export const skillFormSchema = z.object({
  displayName: z.string().optional().nullable(),
  description: z.string().optional().nullable(),
  skillType: z.enum(["instructional", "procedural"]),
  instructionMarkdown: z.string().optional().nullable(),
  slashCommand: z.string().optional().nullable(),
  category: z.string().optional().nullable(),
  tags: z.array(z.string()).optional().nullable(),
  status: registryStatusEnum,
});

export type SkillFormValues = z.infer<typeof skillFormSchema>;

// ---------------------------------------------------------------------------
// Field-level validation helper
// ---------------------------------------------------------------------------

/**
 * Validate a single field against a Zod schema.
 * Returns an error message string on failure, or null on success.
 */
export function validateField<T extends z.ZodTypeAny>(
  schema: T,
  fieldName: string,
  value: unknown,
): string | null {
  // Extract the field schema if the top-level is an object schema
  const shape = (schema as unknown as { shape?: Record<string, z.ZodTypeAny> })
    .shape;
  if (!shape || !(fieldName in shape)) {
    return null;
  }
  const fieldSchema = shape[fieldName];
  if (!fieldSchema) return null;
  const result = fieldSchema.safeParse(value);
  if (result.success) return null;
  return result.error.issues[0]?.message ?? "Invalid value";
}
