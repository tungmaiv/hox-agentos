/**
 * /admin/access → redirect to /admin/users (first sub-page in Access tab).
 */
import { redirect } from "next/navigation";

export default function AccessPage() {
  redirect("/admin/users");
}
