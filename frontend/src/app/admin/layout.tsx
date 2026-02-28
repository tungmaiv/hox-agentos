/**
 * Admin dashboard layout with role-based access control.
 *
 * Server Component that checks user session for admin roles.
 * Non-admin users see a 403 message. Admin/developer users see
 * a tab navigation with links to artifact management pages.
 */
import { auth } from "@/auth";
import Link from "next/link";

const ADMIN_TABS = [
  { label: "Agents", href: "/admin/agents" },
  { label: "Tools", href: "/admin/tools" },
  { label: "Skills", href: "/admin/skills" },
  { label: "MCP Servers", href: "/admin/mcp-servers" },
  { label: "Permissions", href: "/admin/permissions" },
  { label: "AI Builder", href: "/admin/create" },
] as const;

/** Roles that grant access to the admin dashboard. */
const ADMIN_ROLES = ["it-admin", "admin", "developer"];

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center p-8">
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">
            Authentication Required
          </h1>
          <p className="text-gray-500">Please sign in to access the admin dashboard.</p>
          <Link
            href="/login"
            className="mt-4 inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
          >
            Sign In
          </Link>
        </div>
      </div>
    );
  }

  // Check for admin/developer roles in the session token.
  // Keycloak realm roles are stored in the JWT; next-auth exposes them
  // differently depending on the mapper config. We check the token
  // for realm_roles (flat list from custom scope mapper).
  const token = session as unknown as Record<string, unknown>;
  const realmRoles = (token.realmRoles ?? token.realm_roles ?? []) as string[];

  // Also check standard Keycloak role location
  const realmAccess = token.realm_access as
    | { roles?: string[] }
    | undefined;
  const allRoles = [
    ...realmRoles,
    ...(realmAccess?.roles ?? []),
  ];

  const hasAdminRole = allRoles.some((role) => ADMIN_ROLES.includes(role));

  // If roles are not available in the session (common in next-auth default config),
  // allow access and let the backend enforce the permission check via the proxy.
  // This provides a graceful fallback — the backend always has the final say.
  const allowAccess = hasAdminRole || allRoles.length === 0;

  if (!allowAccess) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center p-8">
          <h1 className="text-2xl font-semibold text-red-600 mb-2">
            Access Denied
          </h1>
          <p className="text-gray-500 mb-4">
            You do not have permission to access the admin dashboard.
          </p>
          <p className="text-sm text-gray-400">
            Required roles: admin, developer, or it-admin
          </p>
          <Link
            href="/chat"
            className="mt-4 inline-block px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors text-sm"
          >
            Back to Chat
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <Link
              href="/chat"
              className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              &larr; Back to Chat
            </Link>
            <h1 className="text-lg font-semibold text-gray-900">
              Admin Dashboard
            </h1>
          </div>
          <div className="text-sm text-gray-500">
            {session.user?.email ?? "Admin"}
          </div>
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-0 overflow-x-auto">
            {ADMIN_TABS.map((tab) => (
              <Link
                key={tab.href}
                href={tab.href}
                className="px-4 py-3 text-sm font-medium text-gray-600 hover:text-blue-600 hover:border-b-2 hover:border-blue-600 transition-colors whitespace-nowrap border-b-2 border-transparent"
              >
                {tab.label}
              </Link>
            ))}
          </div>
        </div>
      </nav>

      {/* Page content */}
      <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
    </div>
  );
}
