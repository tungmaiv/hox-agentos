/**
 * System sub-section layout.
 *
 * The parent admin/layout.tsx already renders the System sub-nav for all paths
 * under /admin/config, /admin/identity, /admin/system/*, and /admin/memory.
 * This layout simply renders children — it is a Next.js segment boundary for
 * the /admin/system/* URL space.
 */
export default function SystemLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
