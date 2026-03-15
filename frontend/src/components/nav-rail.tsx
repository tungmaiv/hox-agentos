"use client";
/**
 * NavRail — dark vertical navigation rail for desktop screens.
 *
 * Visible on md+ breakpoints (hidden on mobile — MobileTabBar handles mobile).
 * 64px wide, fixed to the left side, full viewport height.
 *
 * Items:
 *  - Top group: Chat, Workflows, Skills
 *  - Bottom group: Admin (role-gated), Settings, Avatar (Profile + SignOut dropdown)
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { useState, useRef, useEffect } from "react";
import {
  MessageSquare,
  GitBranch,
  Zap,
  HardDrive,
  Shield,
  Settings,
} from "lucide-react";
import { SignOutButton } from "@/components/sign-out-button";
import UserNotificationBell from "@/components/user-notification-bell";

const ADMIN_ROLES = ["admin", "developer", "it-admin"];

interface NavItemProps {
  href: string;
  icon: React.ReactNode;
  label: string;
  active: boolean;
}

function NavItem({ href, icon, label, active }: NavItemProps) {
  return (
    <Link
      href={href}
      title={label}
      className={`relative flex flex-col items-center justify-center w-full h-14 transition-colors group ${
        active
          ? "border-l-[3px] border-blue-500 bg-white/10 text-white"
          : "border-l-[3px] border-transparent text-gray-400 hover:bg-white/5 hover:text-gray-200"
      }`}
    >
      <span className="flex items-center justify-center w-6 h-6">{icon}</span>
      {/* Tooltip on hover */}
      <span className="absolute left-full ml-2 px-2 py-1 text-xs bg-gray-800 text-white rounded shadow-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
        {label}
      </span>
    </Link>
  );
}

export function NavRail() {
  const pathname = usePathname();
  const { data: session } = useSession();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Determine active route (match on prefix)
  const isActive = (prefix: string) => pathname.startsWith(prefix);

  // Role check for admin visibility
  const token = session as unknown as Record<string, unknown> | null;
  const realmRoles = (
    (token?.realmRoles ?? token?.realm_roles ?? []) as string[]
  ).concat(
    ((token?.realm_access as { roles?: string[] } | undefined)?.roles ?? [])
  );
  const showAdmin = realmRoles.some((r) => ADMIN_ROLES.includes(r));

  // User initial for avatar
  const userInitial =
    session?.user?.name?.charAt(0)?.toUpperCase() ??
    session?.user?.email?.charAt(0)?.toUpperCase() ??
    "U";

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [dropdownOpen]);

  return (
    <nav
      className="hidden md:flex flex-col fixed left-0 top-0 h-screen w-16 z-50"
      style={{ backgroundColor: "#1e1e2e" }}
      aria-label="Main navigation"
    >
      {/* Logo / monogram */}
      <div className="flex items-center justify-center h-14 shrink-0">
        <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center">
          <span className="text-white font-bold text-sm select-none">B</span>
        </div>
      </div>

      {/* Top group — primary navigation */}
      <div className="flex-1 flex flex-col pt-2">
        <NavItem
          href="/chat"
          icon={<MessageSquare size={20} />}
          label="Chat"
          active={isActive("/chat")}
        />
        <NavItem
          href="/workflows"
          icon={<GitBranch size={20} />}
          label="Workflows"
          active={isActive("/workflows")}
        />
        <NavItem
          href="/skills"
          icon={<Zap size={20} />}
          label="Skills"
          active={isActive("/skills")}
        />
        <NavItem
          href="/files"
          icon={<HardDrive size={20} />}
          label="Files"
          active={isActive("/files")}
        />
      </div>

      {/* Bottom group — admin, settings, profile */}
      <div className="flex flex-col pb-2">
        {showAdmin && (
          <NavItem
            href="/admin"
            icon={<Shield size={20} />}
            label="Admin"
            active={isActive("/admin")}
          />
        )}
        <NavItem
          href="/settings"
          icon={<Settings size={20} />}
          label="Settings"
          active={isActive("/settings")}
        />

        {/* User notification bell — share notifications */}
        <UserNotificationBell />

        {/* Avatar dropdown — Profile + SignOut */}
        <div ref={dropdownRef} className="relative">
          <button
            type="button"
            title="Profile"
            onClick={() => setDropdownOpen((prev) => !prev)}
            className="flex items-center justify-center w-full h-14 text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-colors"
            aria-haspopup="true"
            aria-expanded={dropdownOpen}
          >
            <div className="w-8 h-8 rounded-full bg-blue-700 flex items-center justify-center">
              <span className="text-white text-sm font-semibold select-none">
                {userInitial}
              </span>
            </div>
          </button>

          {dropdownOpen && (
            <div className="absolute left-full bottom-2 ml-2 w-44 bg-white border border-gray-200 rounded-lg shadow-xl py-1 z-50">
              <Link
                href="/profile"
                className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                onClick={() => setDropdownOpen(false)}
              >
                Profile
              </Link>
              <div className="border-t border-gray-100 my-1" />
              <div className="px-4 py-2">
                <SignOutButton />
              </div>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
