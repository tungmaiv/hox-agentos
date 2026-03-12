/**
 * Access sub-section layout.
 *
 * The parent admin/layout.tsx already renders the Access sub-nav for all paths
 * under /admin/users, /admin/permissions, and /admin/credentials.
 * This layout simply renders children — it is a Next.js segment boundary for
 * the /admin/access/* URL space.
 */
export default function AccessLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
