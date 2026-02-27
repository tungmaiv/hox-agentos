import type { NodeStatus } from "@/hooks/use-workflow-run";

const RING: Record<NodeStatus, string> = {
  idle:              "border-gray-200 bg-white",
  running:           "border-blue-400 bg-blue-50 animate-pulse",
  completed:         "border-green-500 bg-green-50",
  failed:            "border-red-500 bg-red-50",
  awaiting_approval: "border-yellow-400 bg-yellow-50",
};

interface Props {
  status: NodeStatus;
  children: React.ReactNode;
  className?: string;
}

export function NodeStatusRing({ status, children, className = "" }: Props) {
  return (
    <div
      className={`border-2 rounded-lg p-3 min-w-40 shadow-sm transition-colors ${RING[status]} ${className}`}
    >
      {children}
    </div>
  );
}
