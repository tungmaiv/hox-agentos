/**
 * Enhanced AI Builder — Phase 23 artifact builder with:
 * - Full skill/tool content generation in one shot
 * - Find Similar (pgvector cosine search over skill_repo_index)
 * - Fork external skills into draft
 * - Edit JSON toggle
 * - Security gate on save (SecurityReportCard)
 */
import { ArtifactBuilderClient } from "@/components/admin/artifact-builder-client";

export default function EnhancedBuilderPage() {
  return <ArtifactBuilderClient />;
}
