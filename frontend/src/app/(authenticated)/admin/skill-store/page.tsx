"use client";
/**
 * Admin Skill Store page — sub-tab navigation between Repositories and Browse.
 *
 * Uses client-side tab state. Admins see both tabs; the page is accessible
 * to any user who has access to the /admin area (access enforced by admin layout).
 *
 * Repositories tab: admin-only UI for managing external repos
 * Browse tab: available to all admin users for skill discovery and import
 */
import { useState } from "react";
import { SkillStoreRepositories } from "@/components/admin/skill-store-repositories";
import { SkillStoreBrowse } from "@/components/admin/skill-store-browse";

type SubTab = "browse" | "repositories";

export default function SkillStorePage() {
  const [activeTab, setActiveTab] = useState<SubTab>("browse");

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Skill Store</h1>
        <p className="text-sm text-gray-500 mt-1">
          Browse and import skills from external repositories. Admins can add
          and manage repositories.
        </p>
      </div>

      {/* Sub-tab navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-0 -mb-px">
          <button
            onClick={() => setActiveTab("browse")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "browse"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            Browse Skills
          </button>
          <button
            onClick={() => setActiveTab("repositories")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "repositories"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            Repositories
          </button>
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "browse" && <SkillStoreBrowse />}
      {activeTab === "repositories" && <SkillStoreRepositories />}
    </div>
  );
}
