/**
 * Authentication header — Server Component.
 *
 * Reads the next-auth session server-side and renders the user's email
 * and a sign-out button. No useSession() needed because this is a Server
 * Component — session data is accessed directly via auth().
 *
 * Shows nothing if there is no session (caller is responsible for redirecting
 * unauthenticated users before rendering this component).
 */
import { auth } from "@/auth";
import { SignOutButton } from "./sign-out-button";

export async function AuthHeader() {
  const session = await auth();
  if (!session?.user) return null;

  return (
    <header className="border-b p-4 flex items-center justify-between bg-white">
      <h1 className="font-semibold text-gray-900">Blitz AgentOS</h1>
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">{session.user.email}</span>
        <SignOutButton />
      </div>
    </header>
  );
}
