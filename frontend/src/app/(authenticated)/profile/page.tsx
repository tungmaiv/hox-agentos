/**
 * Profile page — account info, custom instructions, LLM preferences, sign out.
 *
 * Replaces the Plan 16-02 placeholder with the full implementation.
 * Server Component page shell; all interactive sections are Client Components.
 *
 * Sections (in order):
 *   1. AccountInfoCard — name, email, auth provider badge, roles, session expiry
 *   2. CustomInstructionsCard — textarea with manual Save (moved from /settings)
 *   3. LLMPreferencesCard — thinking mode toggle + response style radio (auto-save)
 *   4. PasswordChangeCard — inline expandable form (local auth users only)
 *   5. SignOutButton — at the bottom of the page
 *
 * Mobile: Admin link visible to admin-role users (no 6th tab on mobile nav).
 * Per CONTEXT.md: "Admin access on mobile: link on the profile page, visible
 * only to admin-role users".
 */
import Link from "next/link";
import { auth } from "@/auth";
import { SignOutButton } from "@/components/sign-out-button";
import { AccountInfoCard } from "@/components/profile/account-info-card";
import { PasswordChangeCard } from "@/components/profile/password-change-card";
import { CustomInstructionsCard } from "@/components/profile/custom-instructions-card";
import { LLMPreferencesCard } from "@/components/profile/llm-preferences-card";

const ADMIN_ROLES = ["admin", "developer", "it-admin"];

export default async function ProfilePage() {
  const session = await auth();
  const token = session as unknown as Record<string, unknown> | null;
  const realmRoles = (token?.realmRoles ?? []) as string[];
  const showAdminLink = realmRoles.some((r) => ADMIN_ROLES.includes(r));

  return (
    <main className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Profile</h1>

      <div className="space-y-6">
        <AccountInfoCard />
        <CustomInstructionsCard />
        <LLMPreferencesCard />
        <PasswordChangeCard />

        {/* Admin link — mobile only, visible to admin-role users */}
        {showAdminLink && (
          <div className="md:hidden">
            <Link
              href="/admin"
              className="flex items-center gap-2 p-4 bg-white rounded-lg border border-gray-200 shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <svg
                className="w-4 h-4 text-gray-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
              Admin Panel
            </Link>
          </div>
        )}

        {/* Sign out */}
        <div className="pt-2 pb-4 border-t border-gray-100">
          <div className="flex items-center gap-3">
            <SignOutButton />
          </div>
        </div>
      </div>
    </main>
  );
}
