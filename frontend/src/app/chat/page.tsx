// frontend/src/app/chat/page.tsx
import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { ChatLayout } from "@/components/chat/chat-layout";
import type { Conversation } from "@/components/chat/chat-layout";

async function fetchConversations(accessToken: string): Promise<Conversation[]> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${apiUrl}/api/conversations/?limit=20`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (!response.ok) return [];
    return (await response.json()) as Conversation[];
  } catch {
    return [];
  }
}

export default async function ChatPage() {
  const session = await auth();
  if (!session) redirect("/login");

  const accessToken = (session as unknown as Record<string, unknown>)
    .accessToken as string | undefined;
  const conversations = accessToken
    ? await fetchConversations(accessToken)
    : [];

  return (
    <ChatLayout
      initialConversations={conversations}
      userEmail={session.user?.email ?? ""}
    />
  );
}
