// frontend/src/app/settings/integrations/page.tsx
/**
 * Settings → Integrations stub page.
 * Server Component — no client interactivity needed for stub.
 *
 * Full MCP server CRUD management is implemented in Phase 3 plan 03-03.
 * This stub provides navigation structure and a placeholder UI.
 */

import Link from "next/link";

export default function IntegrationsSettingsPage() {
  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="mb-6">
        <Link
          href="/settings"
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Settings
        </Link>
      </div>

      <h1 className="text-2xl font-semibold mb-2">Integrations</h1>
      <p className="text-sm text-gray-500 mb-8">
        Connect MCP servers to extend Blitz with external tools and data
        sources. Full management UI is available in Phase 3 (03-03).
      </p>

      <section className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
          <h2 className="text-sm font-medium text-gray-700">
            MCP Server Management — Available in Phase 3 (03-03)
          </h2>
        </div>

        <ul className="divide-y divide-gray-100">
          <li className="flex items-center justify-between px-4 py-3">
            <div>
              <p className="text-sm font-medium text-gray-900">CRM Server</p>
              <p className="text-xs text-gray-400 mt-0.5">
                http://mcp-crm:8001 — not yet configured
              </p>
            </div>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
              Coming soon
            </span>
          </li>
        </ul>

        <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            MCP servers will be configurable via admin UI in plan 03-03. Until
            then, servers are registered directly in the database.
          </p>
        </div>
      </section>
    </main>
  );
}
