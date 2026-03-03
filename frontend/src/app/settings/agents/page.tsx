// frontend/src/app/settings/agents/page.tsx
/**
 * Permanent redirect: /settings/agents → /admin/config
 *
 * Agent configuration moved to the unified admin dashboard (Phase 12, plan 01).
 * This file is kept (not deleted) to return a proper HTTP redirect instead of 404.
 * Server Component: redirect() from next/navigation works at render time.
 */
import { redirect } from "next/navigation";

export default function SettingsAgentsPage() {
  redirect("/admin/config");
}
