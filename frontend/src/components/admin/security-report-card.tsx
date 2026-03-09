"use client";
/**
 * SecurityReportCard — displays security scan results after builder-save.
 *
 * Shows trust score, factor breakdown progress bars, injection warnings,
 * recommendation badge, and "Approve & Activate" button for pending_review skills.
 */
import { useState } from "react";

export interface SecurityReportData {
  score: number;
  factors: Record<string, number>;
  recommendation: "approve" | "review" | "reject";
  injection_matches: string[];
}

interface SecurityReportCardProps {
  skillId: string;
  report: SecurityReportData;
  onApproved: () => void;
}

/** Human-readable factor labels */
const FACTOR_LABELS: Record<string, string> = {
  source_reputation: "Source Reputation",
  tool_scope: "Tool Scope",
  prompt_safety: "Prompt Safety",
  complexity: "Complexity",
  dependency_risk: "Dependency Risk",
  data_flow_risk: "Data Flow Risk",
};

function RecommendationBadge({
  recommendation,
}: {
  recommendation: "approve" | "review" | "reject";
}) {
  const styles: Record<string, string> = {
    approve:
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800",
    review:
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800",
    reject:
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800",
  };
  const labels: Record<string, string> = {
    approve: "Approved",
    review: "Needs Review",
    reject: "Rejected",
  };
  return <span className={styles[recommendation]}>{labels[recommendation]}</span>;
}

export function SecurityReportCard({
  skillId,
  report,
  onApproved,
}: SecurityReportCardProps) {
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  const scoreColor =
    report.recommendation === "approve"
      ? "text-green-600"
      : report.recommendation === "review"
        ? "text-yellow-600"
        : "text-red-600";

  const handleApprove = async () => {
    const confirmed = window.confirm(
      "This skill has security concerns. Approving will activate it for all users. Continue?"
    );
    if (!confirmed) return;

    setApproving(true);
    setApproveError(null);

    try {
      const res = await fetch(`/api/admin/skills/${skillId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: "approve" }),
      });

      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as Record<
          string,
          unknown
        >;
        let errMsg = `HTTP ${res.status}`;
        if (typeof body.detail === "string") {
          errMsg = body.detail;
        }
        throw new Error(errMsg);
      }

      onApproved();
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white space-y-4">
      {/* Header: score + badge */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wide font-medium mb-1">
            Trust Score
          </p>
          <p className={`text-4xl font-bold ${scoreColor}`}>
            {report.score}
            <span className="text-lg font-normal text-gray-400">/100</span>
          </p>
        </div>
        <RecommendationBadge recommendation={report.recommendation} />
      </div>

      {/* Factor breakdown */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-gray-700">Factor Breakdown</p>
        {Object.entries(report.factors).map(([factor, factorScore]) => (
          <div key={factor}>
            <div className="flex justify-between text-xs text-gray-600 mb-0.5">
              <span>{FACTOR_LABELS[factor] ?? factor}</span>
              <span className="font-medium">{factorScore}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div
                className="bg-blue-500 h-1.5 rounded-full transition-all"
                style={{ width: `${Math.min(100, Math.max(0, factorScore))}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Injection warnings */}
      {report.injection_matches.length > 0 && (
        <div className="border border-red-200 bg-red-50 rounded-md p-3">
          <p className="text-xs font-semibold text-red-700 mb-1">
            Injection Pattern Warnings
          </p>
          <ul className="space-y-0.5">
            {report.injection_matches.map((match, i) => (
              <li key={i} className="text-xs text-red-600 font-mono">
                &bull; {match}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Approve & Activate (only for review/reject) */}
      {report.recommendation !== "approve" && (
        <div className="pt-2 border-t border-gray-100">
          <button
            onClick={handleApprove}
            disabled={approving}
            className="w-full px-3 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {approving ? "Approving..." : "Approve & Activate"}
          </button>
          {approveError && (
            <p className="mt-2 text-xs text-red-600">{approveError}</p>
          )}
        </div>
      )}
    </div>
  );
}
