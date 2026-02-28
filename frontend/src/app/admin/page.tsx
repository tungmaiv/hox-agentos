/**
 * Admin dashboard root page — redirects to /admin/agents (first tab).
 */
import { redirect } from "next/navigation";

export default function AdminPage() {
  redirect("/admin/agents");
}
