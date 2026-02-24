import { auth } from "@/auth";
import { redirect } from "next/navigation";

/**
 * Chat page — protected route.
 * Redirects to /login if not authenticated.
 * Full AG-UI chat interface implemented in Phase 2.
 */
export default async function ChatPage() {
  const session = await auth();
  if (!session) {
    redirect("/login");
  }

  return (
    <main className="flex min-h-screen flex-col">
      <header className="border-b p-4 flex items-center justify-between">
        <h1 className="font-semibold">Blitz AgentOS</h1>
        <span className="text-sm text-gray-600">{session.user?.email}</span>
      </header>
      <div className="flex-1 p-4">
        <p className="text-gray-400">Chat interface coming in Phase 2.</p>
      </div>
    </main>
  );
}
