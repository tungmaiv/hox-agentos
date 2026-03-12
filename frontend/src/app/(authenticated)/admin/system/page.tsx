/**
 * /admin/system → redirect to /admin/config (first sub-page in System tab).
 */
import { redirect } from "next/navigation";

export default function SystemPage() {
  redirect("/admin/config");
}
