/**
 * /files — File Manager page shell.
 * Server Component — FileManager is loaded via client wrapper to allow ssr: false.
 */
import { FileManagerLoader } from "./_components/file-manager-loader";

export const metadata = {
  title: "Files | Blitz AgentOS",
};

export default function FilesPage() {
  return (
    <main className="h-full">
      <FileManagerLoader />
    </main>
  );
}
