import { redirect } from "next/navigation";

// Middleware handles unauthenticated users: they are redirected to /login
// before this page renders. Authenticated users are sent directly to /chat.
export default function Home() {
  redirect("/chat");
}

