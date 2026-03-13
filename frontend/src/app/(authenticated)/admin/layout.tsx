"use client";
/**
 * Admin dashboard layout with role-based access control and 4-tab grouped navigation.
 *
 * Client Component — needs usePathname() to highlight active tab and show sub-nav.
 *
 * 4-tab structure:
 *   Registry — hub page with entity counts + navigation links
 *   Access   — Users, Permissions, Credentials sub-nav
 *   System   — Config, Identity, LLM, Memory sub-nav
 *   Build    — Artifact Builder, Skill Store, Create sub-nav
 */
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";

// ---------------------------------------------------------------------------
// Tab / sub-nav definitions
// ---------------------------------------------------------------------------

const REGISTRY_PATHS = ["/admin/agents", "/admin/skills", "/admin/tools", "/admin/mcp-servers"];

const ACCESS_SUBNAV = [
  { label: "Users", href: "/admin/users" },
  { label: "Permissions", href: "/admin/permissions" },
  { label: "Credentials", href: "/admin/credentials" },
];
const ACCESS_PATHS = ACCESS_SUBNAV.map((s) => s.href);

const SYSTEM_SUBNAV = [
  { label: "Config", href: "/admin/config" },
  { label: "Identity", href: "/admin/identity" },
  { label: "LLM", href: "/admin/system/llm" },
  { label: "Memory", href: "/admin/memory" },
];
const SYSTEM_PATHS = ["/admin/config", "/admin/identity", "/admin/system", "/admin/memory"];

const BUILD_SUBNAV = [
  { label: "Artifact Builder", href: "/admin/builder" },
  { label: "Skill Store", href: "/admin/skill-store" },
  { label: "Create", href: "/admin/create" },
];
const BUILD_PATHS = BUILD_SUBNAV.map((s) => s.href);

const TOP_TABS = [
  { label: "Registry", href: "/admin", matchPaths: REGISTRY_PATHS, exactMatch: true },
  { label: "Access", href: "/admin/users", matchPaths: ACCESS_PATHS, exactMatch: false },
  { label: "System", href: "/admin/config", matchPaths: SYSTEM_PATHS, exactMatch: false },
  { label: "Build", href: "/admin/create", matchPaths: BUILD_PATHS, exactMatch: false },
];

/** Roles that grant access to the admin dashboard. */
const ADMIN_ROLES = ["it-admin", "admin", "developer"];

// ---------------------------------------------------------------------------
// Helper: determine which top-level tab is active
// ---------------------------------------------------------------------------

function getActiveTab(pathname: string): "registry" | "access" | "system" | "build" {
  if (ACCESS_PATHS.some((p) => pathname.startsWith(p))) return "access";
  if (SYSTEM_PATHS.some((p) => pathname.startsWith(p))) return "system";
  if (BUILD_PATHS.some((p) => pathname.startsWith(p))) return "build";
  return "registry";
}

// ---------------------------------------------------------------------------
// Layout component
// ---------------------------------------------------------------------------

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: session } = useSession();

  // Bell icon state — pending_activation skills
  const [pendingCount, setPendingCount] = useState(0);
  const [bellOpen, setBellOpen] = useState(false);
  const [pendingSkills, setPendingSkills] = useState<Array<{ id: string; name: string }>>([]);

  useEffect(() => {
    const fetchPending = async () => {
      try {
        const token = session?.accessToken;
        if (!token) return;
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/registry?type=skill&status=pending_activation`,
          {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
          }
        );
        if (!res.ok) return;
        const data = (await res.json()) as Array<{ id: string; name: string }>;
        setPendingCount(data.length);
        setPendingSkills(data);
      } catch {
        // Bell is non-critical — swallow errors
      }
    };
    void fetchPending();
  }, [session]);

  // Role check — mirrors server-side logic; backend RBAC is the final gate
  const token = session as unknown as Record<string, unknown>;
  const realmRoles = (token?.realmRoles ?? token?.realm_roles ?? []) as string[];
  const realmAccess = token?.realm_access as { roles?: string[] } | undefined;
  const allRoles = [...realmRoles, ...(realmAccess?.roles ?? [])];
  const hasAdminRole = allRoles.some((role) => ADMIN_ROLES.includes(role));

  if (session !== undefined && !hasAdminRole) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center p-8">
          <h1 className="text-2xl font-semibold text-red-600 mb-2">Access Denied</h1>
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

  const activeTab = getActiveTab(pathname);

  // Sub-nav items for the active tab (null = Registry, which has no sub-nav)
  const subNav =
    activeTab === "access"
      ? ACCESS_SUBNAV
      : activeTab === "system"
      ? SYSTEM_SUBNAV
      : activeTab === "build"
      ? BUILD_SUBNAV
      : null;

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
            <h1 className="text-lg font-semibold text-gray-900">Admin Dashboard</h1>
          </div>
          <div className="flex items-center gap-3">
            {/* Pending skills bell */}
            <div className="relative">
              <button
                onClick={() => setBellOpen((prev) => !prev)}
                className="relative p-1 rounded hover:bg-gray-100 transition-colors"
                title="Skills pending activation"
              >
                🔔
                {pendingCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-orange-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center leading-none">
                    {pendingCount}
                  </span>
                )}
              </button>
              {bellOpen && (
                <div className="absolute right-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50 p-2">
                  <p className="text-xs font-semibold text-gray-500 mb-1 px-2">Skills pending activation</p>
                  {pendingSkills.length === 0 ? (
                    <p className="text-xs text-gray-400 px-2 py-1">No skills pending activation</p>
                  ) : (
                    pendingSkills.map((skill) => (
                      <a
                        key={skill.id}
                        href="/admin/skills"
                        className="block text-sm text-gray-700 hover:bg-gray-50 px-2 py-1 rounded"
                        onClick={() => setBellOpen(false)}
                      >
                        {skill.name}
                      </a>
                    ))
                  )}
                </div>
              )}
            </div>
            <div className="text-sm text-gray-500">{session?.user?.email ?? "Admin"}</div>
          </div>
        </div>
      </header>

      {/* Primary 4-tab navigation */}
      <nav className="relative z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-0">
            {TOP_TABS.map((tab) => {
              const isActive = tab.exactMatch
                ? activeTab === "registry"
                : activeTab === tab.label.toLowerCase();
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`px-4 py-3 text-sm font-medium transition-colors whitespace-nowrap border-b-2 ${
                    isActive
                      ? "text-blue-600 border-blue-600"
                      : "text-gray-600 border-transparent hover:text-blue-600 hover:border-blue-300"
                  }`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Secondary sub-navigation (Access / System / Build tabs only) */}
      {subNav && (
        <nav className="bg-gray-50 border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-6">
            <div className="flex gap-1 py-2">
              {subNav.map((item) => {
                const isSubActive =
                  pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                      isSubActive
                        ? "bg-blue-100 text-blue-700"
                        : "text-gray-500 hover:text-gray-900 hover:bg-gray-100"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        </nav>
      )}

      {/* Page content */}
      <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
    </div>
  );
}
