import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { AuthHeader } from "@/components/auth-header";

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
      <AuthHeader />
      <div className="flex-1 p-4">
        <p className="text-gray-400">Chat interface coming in Phase 2.</p>
      </div>
    </main>
  );
}
