import type { Run } from "./types";

export const CATEGORY_COLORS: Record<string, string> = {
  security: "#dc2626",
  dependency: "#d97706",
  deprecation: "#7c3aed",
  tests: "#16a34a",
  documentation: "#2563eb",
  code_quality: "#0d9488",
  other: "#64748b",
};

export const CATEGORY_LABEL: Record<string, string> = {
  security: "Security",
  dependency: "Dependencies",
  deprecation: "Deprecation",
  tests: "Tests",
  documentation: "Docs",
  code_quality: "Code Quality",
  other: "Other",
};

export function categoryColor(cat: string): string {
  return CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.other;
}

export function timeAgo(ts: number): string {
  const secs = Math.max(0, Date.now() / 1000 - ts);
  if (secs < 60) return `${Math.floor(secs)}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export function elapsed(ts: number): string {
  const secs = Math.max(0, Date.now() / 1000 - ts);
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

export function fmtDuration(secs: number | null): string {
  if (secs == null) return "\u2014";
  const m = Math.floor(secs / 60);
  if (m < 1) return `${Math.floor(secs)}s`;
  if (m < 60) return `${m}m`;
  return `${(m / 60).toFixed(1)}h`;
}

/** A coarse human-facing label for the run's lifecycle state. */
export function runState(run: Run): {
  label: string;
  color: string;
  dot: string;
  active?: boolean;
} {
  if (run.status === "error")
    return { label: "Error", color: "#dc2626", dot: "#dc2626" };
  if (run.pr_state === "merged")
    return { label: "Merged", color: "#16a34a", dot: "#16a34a" };
  if (run.needs_attention)
    return { label: "Needs review", color: "#d97706", dot: "#d97706" };
  if (run.has_pr) return { label: "PR open", color: "#2563eb", dot: "#2563eb" };
  if (run.is_active)
    return { label: "Working", color: "#2563eb", dot: "#2563eb", active: true };
  return { label: run.status, color: "#64748b", dot: "#64748b" };
}

export function Badge({
  children,
  color,
}: {
  children: React.ReactNode;
  color: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ color, background: `${color}14`, border: `1px solid ${color}30` }}
    >
      {children}
    </span>
  );
}

export function Dot({ color, active }: { color: string; active?: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${active ? "pulse" : ""}`}
      style={{ background: color }}
    />
  );
}
