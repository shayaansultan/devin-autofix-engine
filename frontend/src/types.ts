export interface StructuredOutput {
  pr_url?: string;
  summary?: string;
  issue_type?: string;
  files_changed?: number;
  key_changes?: string[];
  tests_passed?: boolean;
  verification?: string;
  risk_level?: "low" | "medium" | "high";
  confidence?: "high" | "medium" | "low";
  estimated_human_minutes?: number;
  blockers?: string;
}

export interface SessionMessage {
  event_id: string;
  source: "devin" | "user";
  message: string;
  created_at: number;
}

export interface Run {
  repo: string;
  issue_number: number;
  issue_title: string;
  issue_url: string;
  issue_category: string;
  trigger_type: string;
  triggered_by: string;
  triggered_at: number;
  session_id: string;
  session_url: string;
  status: string;
  status_detail: string | null;
  devin_category: string | null;
  subcategory: string | null;
  acus_consumed: number;
  acus_effective: number;
  acus_estimated: boolean;
  pr_url: string | null;
  pr_state: string | null;
  ci_status: string | null;
  structured_output: StructuredOutput | null;
  updated_at: number;
  is_active: boolean;
  has_pr: boolean;
  needs_attention: boolean;
  time_to_pr_seconds: number | null;
}

export interface Stats {
  total_runs: number;
  active_sessions: number;
  prs_opened: number;
  prs_merged: number;
  success_rate: number;
  merge_rate: number;
  hours_saved: number;
  total_acus: number;
  acus_per_pr: number;
  acus_estimated: boolean;
  acu_usd_rate: number;
  total_cost_usd: number;
  cost_per_pr_usd: number;
  avg_time_to_pr_minutes: number;
  needs_attention: number;
  by_category: Record<string, number>;
}
