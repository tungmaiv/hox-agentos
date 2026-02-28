"use client";
/**
 * useSkills — React hook for fetching available skills from the backend.
 *
 * Fetches from /api/skills (Next.js proxy) on mount.
 * Returns a list of SkillItem objects with name, displayName, description,
 * and optional slashCommand for chat /command autocompletion.
 *
 * The proxy route at /api/skills injects the JWT from the server session
 * so the access token is never exposed to the browser.
 */
import { useState, useEffect } from "react";

export interface SkillItem {
  id: string;
  name: string;
  displayName: string | null;
  description: string | null;
  slashCommand: string | null;
}

interface SkillApiItem {
  id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  slash_command: string | null;
}

function isSkillApiArray(data: unknown): data is SkillApiItem[] {
  return (
    Array.isArray(data) &&
    data.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        "name" in item &&
        "id" in item
    )
  );
}

export function useSkills() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/skills")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: unknown) => {
        if (isSkillApiArray(data)) {
          setSkills(
            data.map((item) => ({
              id: item.id,
              name: item.name,
              displayName: item.display_name,
              description: item.description,
              slashCommand: item.slash_command,
            }))
          );
        }
      })
      .catch(() => setSkills([]))
      .finally(() => setLoading(false));
  }, []);

  return { skills, loading };
}
