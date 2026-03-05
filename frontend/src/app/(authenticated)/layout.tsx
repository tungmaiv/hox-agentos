/**
 * Authenticated route group layout.
 *
 * Wraps all authenticated pages with the NavRail (desktop) and MobileTabBar (mobile).
 * The (authenticated) group does NOT affect URL paths — /chat, /workflows, etc. remain unchanged.
 *
 * Pages that remain OUTSIDE this group (no nav rail):
 *  - /login  (public)
 *  - /api/*  (API routes)
 *  - /       (root redirect)
 */
import { NavRail } from "@/components/nav-rail";
import { MobileTabBar } from "@/components/mobile-tab-bar";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <NavRail />
      <main className="flex-1 md:ml-16">
        {/* Bottom padding on mobile to avoid content hidden behind tab bar */}
        <div className="pb-16 md:pb-0">{children}</div>
      </main>
      <MobileTabBar />
    </div>
  );
}
