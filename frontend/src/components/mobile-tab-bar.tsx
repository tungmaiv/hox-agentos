"use client";
/**
 * MobileTabBar — fixed bottom navigation bar for mobile screens.
 *
 * Visible below the md breakpoint (hidden on desktop — NavRail handles desktop).
 * 5 items: Chat, Workflows, Skills, Settings, Profile.
 * No Admin tab on mobile — admin access is available via Profile > Admin.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, GitBranch, Zap, Settings, User } from "lucide-react";

interface TabItemProps {
  href: string;
  icon: React.ReactNode;
  label: string;
  active: boolean;
}

function TabItem({ href, icon, label, active }: TabItemProps) {
  return (
    <Link
      href={href}
      className={`flex flex-col items-center justify-center flex-1 py-2 gap-0.5 transition-colors ${
        active ? "text-blue-600" : "text-gray-500 hover:text-gray-800"
      }`}
    >
      <span className="w-6 h-6 flex items-center justify-center">{icon}</span>
      <span className="text-[10px] font-medium leading-none">{label}</span>
    </Link>
  );
}

export function MobileTabBar() {
  const pathname = usePathname();
  const isActive = (prefix: string) => pathname.startsWith(prefix);

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 md:hidden bg-white border-t border-gray-200 shadow-md z-40"
      aria-label="Mobile navigation"
    >
      <div className="flex items-stretch h-16">
        <TabItem
          href="/chat"
          icon={<MessageSquare size={22} />}
          label="Chat"
          active={isActive("/chat")}
        />
        <TabItem
          href="/workflows"
          icon={<GitBranch size={22} />}
          label="Workflows"
          active={isActive("/workflows")}
        />
        <TabItem
          href="/skills"
          icon={<Zap size={22} />}
          label="Skills"
          active={isActive("/skills")}
        />
        <TabItem
          href="/settings"
          icon={<Settings size={22} />}
          label="Settings"
          active={isActive("/settings")}
        />
        <TabItem
          href="/profile"
          icon={<User size={22} />}
          label="Profile"
          active={isActive("/profile")}
        />
      </div>
    </nav>
  );
}
