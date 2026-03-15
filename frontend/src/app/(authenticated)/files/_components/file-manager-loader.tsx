"use client";

import dynamic from "next/dynamic";

const FileManager = dynamic(
  () =>
    import("./file-manager").then((m) => ({
      default: m.FileManager,
    })),
  { ssr: false }
);

export function FileManagerLoader() {
  return <FileManager />;
}
