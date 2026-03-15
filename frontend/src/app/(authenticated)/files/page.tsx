/**
 * /files — File Manager page shell.
 * Server Component — FileManager is dynamically imported (client-only).
 */
import dynamic from "next/dynamic";

export const metadata = {
  title: "Files | Blitz AgentOS",
};

const FileManager = dynamic(
  () =>
    import("./_components/file-manager").then((m) => ({
      default: m.FileManager,
    })),
  { ssr: false }
);

export default function FilesPage() {
  return (
    <main className="h-full">
      <FileManager />
    </main>
  );
}
