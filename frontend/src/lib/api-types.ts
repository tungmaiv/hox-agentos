/**
 * Shared Zod schemas and TypeScript types for API responses.
 *
 * Convention: Define Zod schema, then export the inferred type.
 * All external API data MUST be validated through these schemas.
 */
import { z } from "zod";

// ---------------------------------------------------------------------------
// SSO Health
// ---------------------------------------------------------------------------

export const SSOHealthCategorySchema = z.object({
  name: z.string(),
  status: z.enum(["green", "yellow", "red"]),
  detail: z.string(),
});

export type SSOHealthCategory = z.infer<typeof SSOHealthCategorySchema>;

export const CircuitBreakerThresholdsSchema = z.object({
  failure_threshold: z.number(),
  recovery_timeout_seconds: z.number(),
  half_open_max_calls: z.number(),
});

export type CircuitBreakerThresholds = z.infer<
  typeof CircuitBreakerThresholdsSchema
>;

export const CircuitBreakerStateSchema = z.object({
  state: z.string(),
  failure_count: z.number(),
  last_failure_time: z.string().nullable(),
  thresholds: CircuitBreakerThresholdsSchema,
});

export type CircuitBreakerState = z.infer<typeof CircuitBreakerStateSchema>;

export const SSOHealthStatusSchema = z.object({
  overall: z.enum(["healthy", "degraded", "unhealthy"]),
  categories: z.array(SSOHealthCategorySchema),
  circuit_breaker: CircuitBreakerStateSchema,
  checked_at: z.string(),
});

export type SSOHealthStatus = z.infer<typeof SSOHealthStatusSchema>;

// ---------------------------------------------------------------------------
// Admin Notifications
// ---------------------------------------------------------------------------

export const AdminNotificationSchema = z.object({
  id: z.string(),
  category: z.string(),
  severity: z.string(),
  title: z.string(),
  message: z.string(),
  is_read: z.boolean(),
  created_at: z.string(),
  metadata_json: z.unknown().nullable(),
});

export type AdminNotification = z.infer<typeof AdminNotificationSchema>;

export const NotificationCountSchema = z.object({
  total: z.number(),
  unread: z.number(),
});

export type NotificationCount = z.infer<typeof NotificationCountSchema>;
