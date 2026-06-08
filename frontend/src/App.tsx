import { useEffect, useRef, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import {
  fetchRuns,
  fetchStats,
  fetchConfig,
  fetchRunMessages,
  triggerIssue,
} from "./api";
import type { Run, SessionMessage, Stats } from "./types";
import {
  Badge,
  Dot,
  CATEGORY_LABEL,
  categoryColor,
  elapsed,
  fmtDuration,
  runState,
  timeAgo,
} from "./ui";

export default function App() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [cfg, setCfg] = useState<{ repo: string; trigger_label: string } | null>(null);
  const [selected, setSelected] = useState<Run | null>(null);
  const [showTrigger, setShowTrigger] = useState(false);

  async function refresh() {
    try {
      const [r, s] = await Promise.all([fetchRuns(), fetchStats()]);
      setRuns(r);
      setStats(s);
    } catch (e) {
      /* transient */
    }
  }

  useEffect(() => {
    fetchConfig().then(setCfg).catch(() => {});
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  // keep the selected drawer in sync with polled data
  useEffect(() => {
    if (selected) {
      const fresh = runs.find(
        (r) => r.issue_number === selected.issue_number && r.repo === selected.repo
      );
      if (fresh) setSelected(fresh);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs]);

  const active = runs.filter((r) => r.is_active);

  return (
    <div className="min-h-full">
      <Header cfg={cfg} onTrigger={() => setShowTrigger(true)} />

      <div className="mx-auto max-w-[1200px] px-6 pb-16">
        {stats && <KpiCards stats={stats} />}
        {stats && <StatStrip stats={stats} />}

        <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ActiveSessions runs={active} onSelect={setSelected} />
          </div>
          <div>{stats && <CategoryDonut stats={stats} />}</div>
        </div>

        <RunsTable runs={runs} onSelect={setSelected} />
      </div>

      {selected && <RunDrawer run={selected} onClose={() => setSelected(null)} />}
      {showTrigger && (
        <TriggerModal
          repo={cfg?.repo ?? ""}
          onClose={() => setShowTrigger(false)}
          onTriggered={refresh}
        />
      )}
    </div>
  );
}

function Header({
  cfg,
  onTrigger,
}: {
  cfg: { repo: string; trigger_label: string } | null;
  onTrigger: () => void;
}) {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur shadow-sm">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-900">
            Devin Autofix
          </h1>
          <p className="text-sm text-muted">
            {cfg ? (
              <>
                Watching <span className="text-slate-700 font-medium">{cfg.repo}</span> · triggers on
                label{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-700 text-xs">
                  {cfg.trigger_label}
                </code>
              </>
            ) : (
              "\u2026"
            )}
          </p>
        </div>
        <button
          onClick={onTrigger}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 transition-colors"
        >
          + Trigger remediation
        </button>
      </div>
    </header>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">{children}</div>
  );
}

function KpiCards({ stats }: { stats: Stats }) {
  const items = [
    {
      label: "Active sessions",
      value: stats.active_sessions,
      sub: stats.active_sessions > 0 ? "running now" : "idle",
      accent: "#2563eb",
      live: stats.active_sessions > 0,
    },
    {
      label: "PRs opened",
      value: stats.prs_opened,
      sub: `${stats.prs_merged} merged`,
      accent: "#2563eb",
    },
    {
      label: "Success rate",
      value: `${stats.success_rate}%`,
      sub: "produced a PR",
      accent: "#16a34a",
    },
    {
      label: "Est. hours saved",
      value: `${stats.hours_saved}h`,
      sub: "agent-estimated",
      accent: "#7c3aed",
    },
  ];
  return (
    <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
      {items.map((it) => (
        <div key={it.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-muted">
            {it.live && <Dot color={it.accent} active />}
            {it.label}
          </div>
          <div className="mt-2 text-3xl font-bold" style={{ color: it.accent }}>
            {it.value}
          </div>
          <div className="mt-1 text-xs text-muted">{it.sub}</div>
        </div>
      ))}
    </div>
  );
}

function StatStrip({ stats }: { stats: Stats }) {
  const hasRate = stats.acu_usd_rate > 0;
  const est = stats.acus_estimated;
  const items = [
    { label: "Avg time-to-PR", value: `${stats.avg_time_to_pr_minutes}m` },
    { label: "Merge rate", value: `${stats.merge_rate}%` },
    { label: `Total ACUs${est ? " (est.)" : ""}`, value: stats.total_acus.toFixed(1) },
    { label: `ACUs / PR${est ? " (est.)" : ""}`, value: stats.acus_per_pr.toFixed(1) },
    ...(hasRate
      ? [
          { label: "Est. cost / PR", value: `$${stats.cost_per_pr_usd.toFixed(2)}` },
          { label: "Est. total cost", value: `$${stats.total_cost_usd.toFixed(2)}` },
        ]
      : []),
    {
      label: "Needs attention",
      value: stats.needs_attention,
      warn: stats.needs_attention > 0,
    },
  ];
  return (
    <>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {items.map((it) => (
          <div
            key={it.label}
            className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
          >
            <span className="text-xs text-muted">{it.label}</span>
            <span
              className={`text-sm font-semibold ${
                it.warn ? "text-amber-600" : "text-slate-800"
              }`}
            >
              {it.value}
            </span>
          </div>
        ))}
      </div>
      {est && (
        <p className="mt-2 text-[11px] leading-snug text-muted">
          ACU figures are <span className="font-medium">estimated</span> from session runtime
          (~1 ACU / 15 min) × ${stats.acu_usd_rate.toFixed(2)}/ACU — this account doesn&rsquo;t
          expose per-session ACUs via the API. Real ACUs are shown automatically on Enterprise orgs.
        </p>
      )}
    </>
  );
}

function ActiveSessions({
  runs,
  onSelect,
}: {
  runs: Run[];
  onSelect: (r: Run) => void;
}) {
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-800">Active sessions</h2>
        <span className="text-xs text-muted">{runs.length} running</span>
      </div>
      {runs.length === 0 ? (
        <div className="py-10 text-center text-sm text-muted">
          No active sessions. Label an issue{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">devin-autofix</code> or use
          &ldquo;Trigger remediation&rdquo;.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {runs.map((r) => {
            const st = runState(r);
            return (
              <button
                key={r.issue_number}
                onClick={() => onSelect(r)}
                className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-left transition-all hover:border-blue-400 hover:shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">#{r.issue_number}</span>
                  <Badge color={st.color}>
                    <Dot color={st.dot} active={st.active} />
                    {st.label}
                  </Badge>
                </div>
                <div className="mt-1 line-clamp-2 text-sm font-medium text-slate-800">
                  {r.issue_title || `Issue #${r.issue_number}`}
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-muted">
                  <span>{r.status_detail || r.status}</span>
                  <span>{elapsed(r.triggered_at)}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function CategoryDonut({ stats }: { stats: Stats }) {
  const data = Object.entries(stats.by_category).map(([name, value]) => ({
    name,
    value,
  }));
  return (
    <Card>
      <h2 className="mb-2 text-sm font-semibold text-slate-800">By issue type</h2>
      {data.length === 0 ? (
        <div className="py-10 text-center text-sm text-muted">No runs yet</div>
      ) : (
        <div className="flex items-center gap-3">
          <div style={{ width: 130, height: 130 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={data}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={38}
                  outerRadius={60}
                  paddingAngle={2}
                  stroke="none"
                >
                  {data.map((d) => (
                    <Cell key={d.name} fill={categoryColor(d.name)} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex-1 space-y-1.5">
            {data.map((d) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-slate-700">
                  <span
                    className="h-2.5 w-2.5 rounded-sm"
                    style={{ background: categoryColor(d.name) }}
                  />
                  {CATEGORY_LABEL[d.name] ?? d.name}
                </span>
                <span className="text-muted">{d.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function CiBadge({ run }: { run: Run }) {
  if (!run.has_pr) return <span className="text-muted">{"\u2014"}</span>;
  if (run.ci_status === "success") return <Badge color="#16a34a">{"\u2713"} checks</Badge>;
  if (run.ci_status === "failure") return <Badge color="#dc2626">{"\u2717"} checks</Badge>;
  return <Badge color="#64748b">checks{"\u2026"}</Badge>;
}

function RunsTable({ runs, onSelect }: { runs: Run[]; onSelect: (r: Run) => void }) {
  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800">
        All runs
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-4 py-2 font-medium">Issue</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">PR</th>
              <th className="px-4 py-2 font-medium">CI</th>
              <th className="px-4 py-2 font-medium">Conf.</th>
              <th className="px-4 py-2 font-medium">Time{"\u2192"}PR</th>
              <th className="px-4 py-2 font-medium">Saved</th>
              <th className="px-4 py-2 font-medium">When</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-muted">
                  No runs yet.
                </td>
              </tr>
            )}
            {runs.map((r) => {
              const st = runState(r);
              const cat = r.structured_output?.issue_type || r.issue_category;
              const so = r.structured_output;
              return (
                <tr
                  key={r.issue_number}
                  onClick={() => onSelect(r)}
                  className="cursor-pointer border-t border-slate-100 transition-colors hover:bg-slate-50"
                >
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-slate-800">#{r.issue_number}</div>
                    <div className="max-w-[260px] truncate text-xs text-muted">
                      {r.issue_title}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge color={categoryColor(cat)}>
                      {CATEGORY_LABEL[cat] ?? cat}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge color={st.color}>
                      <Dot color={st.dot} active={st.active} />
                      {st.label}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5">
                    {r.pr_url ? (
                      <a
                        href={r.pr_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-blue-600 hover:underline"
                      >
                        {r.pr_url.split("/").pop()
                          ? `#${r.pr_url.split("/").pop()}`
                          : "PR"}
                      </a>
                    ) : (
                      <span className="text-muted">{"\u2014"}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <CiBadge run={r} />
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">
                    {so?.confidence ?? "\u2014"}
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">
                    {fmtDuration(r.time_to_pr_seconds)}
                  </td>
                  <td className="px-4 py-2.5 text-slate-700">
                    {so?.estimated_human_minutes
                      ? `${so.estimated_human_minutes}m`
                      : "\u2014"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted">
                    {timeAgo(r.triggered_at)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RunDrawer({ run, onClose }: { run: Run; onClose: () => void }) {
  const so = run.structured_output;
  const st = runState(run);
  const [tab, setTab] = useState<"log" | "result" | "json">("log");

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-black/40" onClick={onClose}>
      <div
        className="h-full w-full max-w-md overflow-y-auto border-l border-slate-200 bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs text-muted">#{run.issue_number}</div>
            <h3 className="mt-0.5 text-base font-semibold text-slate-900">
              {run.issue_title}
            </h3>
          </div>
          <button onClick={onClose} className="text-muted hover:text-slate-800 transition-colors">
            {"\u2715"}
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <Badge color={st.color}>
            <Dot color={st.dot} active={st.active} />
            {st.label}
          </Badge>
          {so?.confidence && (
            <Badge color="#64748b">confidence: {so.confidence}</Badge>
          )}
          {so?.risk_level && (
            <Badge
              color={
                so.risk_level === "high"
                  ? "#dc2626"
                  : so.risk_level === "medium"
                  ? "#d97706"
                  : "#16a34a"
              }
            >
              risk: {so.risk_level}
            </Badge>
          )}
        </div>

        <div className="mt-4 space-y-3 text-sm">
          <Field label="Trigger">
            {run.trigger_type} · by {run.triggered_by}
          </Field>
          <Field label="Devin session">
            {run.session_url ? (
              <a
                href={run.session_url}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 hover:underline"
              >
                {run.session_url}
              </a>
            ) : (
              "\u2014"
            )}
          </Field>
          <Field label="Pull request">
            {run.pr_url ? (
              <a
                href={run.pr_url}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 hover:underline"
              >
                {run.pr_url}
              </a>
            ) : (
              "not opened yet"
            )}
            {run.pr_state ? ` · ${run.pr_state}` : ""}
            {run.ci_status ? ` · CI ${run.ci_status}` : ""}
          </Field>
          <Field label={`ACUs consumed${run.acus_estimated ? " (est.)" : ""}`}>
            {(run.acus_effective ?? run.acus_consumed).toFixed(2)}
          </Field>
          {run.devin_category && (
            <Field label="Devin category">
              {run.devin_category}
              {run.subcategory ? ` / ${run.subcategory}` : ""}
            </Field>
          )}
        </div>

        <div className="mt-5">
          <div className="mb-3 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
            <button
              onClick={() => setTab("log")}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                tab === "log"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-muted hover:text-slate-700"
              }`}
            >
              Activity log
            </button>
            <button
              onClick={() => setTab("result")}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                tab === "result"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-muted hover:text-slate-700"
              }`}
            >
              Result
            </button>
            <button
              onClick={() => setTab("json")}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                tab === "json"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-muted hover:text-slate-700"
              }`}
            >
              JSON
            </button>
          </div>

          {tab === "json" ? (
            so ? (
              <div className="relative">
                <button
                  onClick={() => navigator.clipboard?.writeText(JSON.stringify(so, null, 2))}
                  className="absolute right-2 top-2 rounded-md border border-slate-700 bg-slate-800 px-2 py-0.5 text-[11px] font-medium text-slate-200 hover:bg-slate-700"
                >
                  Copy
                </button>
                <pre className="max-h-96 overflow-auto rounded-lg border border-slate-200 bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">
                  {JSON.stringify(so, null, 2)}
                </pre>
              </div>
            ) : (
              <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-muted">
                No structured output yet — the session is still working.
              </p>
            )
          ) : tab === "log" ? (
            <ActivityLog run={run} />
          ) : so ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              {so.summary && <p className="text-sm text-slate-800">{so.summary}</p>}
              {so.key_changes && so.key_changes.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {so.key_changes.map((k: string, i: number) => (
                    <li key={i}>{k}</li>
                  ))}
                </ul>
              )}
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted">
                {typeof so.files_changed === "number" && (
                  <div>Files changed: {so.files_changed}</div>
                )}
                {typeof so.tests_passed === "boolean" && (
                  <div>Tests passed: {so.tests_passed ? "yes" : "no"}</div>
                )}
                {typeof so.estimated_human_minutes === "number" && (
                  <div>Human est.: {so.estimated_human_minutes}m</div>
                )}
              </div>
              {so.verification && (
                <p className="mt-3 text-xs text-muted">
                  <span className="text-slate-600">Verification:</span> {so.verification}
                </p>
              )}
              {so.blockers && (
                <p className="mt-2 text-xs text-amber-600">Blockers: {so.blockers}</p>
              )}
            </div>
          ) : (
            <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-muted">
              No result yet — the session is still working.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function ActivityLog({ run }: { run: Run }) {
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let live = true;
    async function load() {
      try {
        const m = await fetchRunMessages(run.repo, run.issue_number);
        if (live) {
          setMessages(m);
          setErr(false);
        }
      } catch {
        if (live) setErr(true);
      } finally {
        if (live) setLoading(false);
      }
    }
    load();
    // poll while the session is active so the log streams in
    const id = run.is_active ? setInterval(load, 3000) : null;
    return () => {
      live = false;
      if (id) clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run.repo, run.issue_number, run.is_active]);

  if (loading) {
    return (
      <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-muted">
        Loading session activity…
      </p>
    );
  }
  if (err) {
    return (
      <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-muted">
        Couldn’t load session activity.
      </p>
    );
  }
  if (messages.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-muted">
        No activity yet.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {messages.map((m) => {
        const isDevin = m.source === "devin";
        return (
          <div key={m.event_id} className="flex flex-col">
            <div className="mb-1 flex items-center gap-2 text-xs">
              <span
                className={`rounded px-1.5 py-0.5 font-medium ${
                  isDevin
                    ? "bg-blue-50 text-blue-700"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {isDevin ? "Devin" : "Trigger"}
              </span>
              <span className="text-muted">{timeAgo(m.created_at)}</span>
            </div>
            <div
              className={`whitespace-pre-wrap rounded-lg border p-3 text-sm ${
                isDevin
                  ? "border-blue-100 bg-blue-50/40 text-slate-800"
                  : "border-slate-200 bg-slate-50 text-slate-700"
              }`}
            >
              {m.message}
            </div>
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 break-words text-slate-800">{children}</div>
    </div>
  );
}

function TriggerModal({
  repo,
  onClose,
  onTriggered,
}: {
  repo: string;
  onClose: () => void;
  onTriggered: () => void;
}) {
  const [n, setN] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function go() {
    setErr("");
    const num = parseInt(n, 10);
    if (!num) {
      setErr("Enter an issue number");
      return;
    }
    setBusy(true);
    try {
      await triggerIssue(num);
      onTriggered();
      onClose();
    } catch (e: any) {
      setErr(e.message || "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold text-slate-900">Trigger remediation</h3>
        <p className="mt-1 text-sm text-muted">
          Manually start a Devin session for an issue in{" "}
          <span className="text-slate-700 font-medium">{repo}</span>. (Same pipeline as the{" "}
          <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">devin-autofix</code> label.)
        </p>
        <input
          autoFocus
          value={n}
          onChange={(e) => setN(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go()}
          placeholder="Issue number, e.g. 2"
          className="mt-4 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-shadow"
        />
        {err && <div className="mt-2 text-xs text-red-600">{err}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={go}
            disabled={busy}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {busy ? "Starting\u2026" : "Start session"}
          </button>
        </div>
      </div>
    </div>
  );
}
