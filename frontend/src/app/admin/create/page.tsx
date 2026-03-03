/**
 * AI-Assisted Artifact Builder — hybrid wizard entry point.
 *
 * Replaced pure-chat builder with split-panel wizard:
 * - Left (45%): structured form with type selector, templates, fields
 * - Right (55%): CopilotKit AI chat assistant with fill_form co-agent tool
 */
import { ArtifactWizard } from "@/components/admin/artifact-wizard";

export default function ArtifactBuilderPage() {
  return <ArtifactWizard />;
}
