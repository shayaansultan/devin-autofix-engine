import type { Run, SessionMessage, Stats } from "./types";

export async function fetchRuns(): Promise<Run[]> {
  const r = await fetch("/api/runs");
  if (!r.ok) throw new Error("failed to fetch runs");
  return (await r.json()).runs;
}

export async function fetchStats(): Promise<Stats> {
  const r = await fetch("/api/stats");
  if (!r.ok) throw new Error("failed to fetch stats");
  return await r.json();
}

export async function fetchConfig(): Promise<{ repo: string; trigger_label: string }> {
  const r = await fetch("/api/config");
  return await r.json();
}

export async function fetchRunMessages(
  repo: string,
  issue_number: number
): Promise<SessionMessage[]> {
  const r = await fetch(`/api/runs/${repo}/${issue_number}/messages`);
  if (!r.ok) throw new Error("failed to fetch messages");
  return (await r.json()).messages;
}

export async function triggerIssue(issue_number: number): Promise<Run> {
  const r = await fetch("/api/trigger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ issue_number }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "trigger failed");
  return await r.json();
}
