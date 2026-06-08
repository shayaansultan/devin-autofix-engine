# Loom Script v4 — Devin Autofix Engine (≈5 min, 1 continuous cut)

Audience: VP of Engineering + senior ICs. Record webcam + screen, one take.

Narrative arc: **problem → live flow → architecture → ROI as the payoff.** Open on the
real backlog (GitHub issues), trigger a fix live, drill into a finished one, explain how
it's built, *then* land on the dashboard numbers as the proof. Don't open cold on stats.

Core technique: **kick off the live Devin session early** (~0:30), let it run in the
background, talk through a finished run + architecture while it works, then glance back.

Each step starts with a **SCREEN:** line telling you exactly what to be looking at.

Timeline at a glance:
- 0:00 What — the problem (on GitHub Issues) — 30s
- 0:30 HERO — trigger a fix live with a label — 45s (then leave it running)
- 1:15 Drill into a finished run — 75s
- 2:30 Architecture (the meat) — 75s
- 3:45 Why Devin, not a script — 25s
- 4:10 ROI — the dashboard numbers as the payoff — 40s
- 4:50 Next steps + close — 10s

---

## 0. Off-camera setup (have these tabs open, in this order)
- **Tab 1 — GitHub Issues** on the fork (you START here): https://github.com/shayaansultan/superset/issues
- **Tab 2 — Dashboard:** full-screen at http://localhost:8000 (2 PRs preloaded: #28, #31).
- **Tab 3 — ARCHITECTURE.md** (rendered, for the diagram): https://github.com/shayaansultan/devin-autofix-engine/blob/demo/ARCHITECTURE.md
- **Tab 4 — app.devin.ai** sessions list (the "behind the scenes" view).
- Logged into GitHub + Devin in this browser. Live-trigger target picked: **#44 (Security: cryptography CVE)** — clean, no label yet. Spare: **#45 (pandas deprecation)**.

---

## 1. WHAT — the problem (0:00–0:30)
**SCREEN:** Tab 1 (GitHub **Issues** list on the fork). Slowly scroll the open issues so the viewer sees the backlog.

> "This is what every engineering org actually looks like — a backlog of small, well-scoped work that never gets done. CVE bumps, deprecations, flaky tests, missing docs. None of it is hard; it's the *volume* that quietly burns senior-engineer hours.
>
> So I built an **event-driven remediation engine on the Devin API** to clear this backlog autonomously. Let me show you the entire workflow — starting right here."

## 2. HERO — trigger a fix live, then let it run (0:30–1:15)
**SCREEN:** Tab 1. Open **#44 (Security: cryptography CVE)**. Apply the **`devin-autofix`** label (Labels gear → check `devin-autofix`). (#45 is a clean spare if you want a second take.)

> "An engineer's whole interface is this: label the issue `devin-autofix`. That's the entire ask — no new tool to learn."

**SCREEN:** Switch to Tab 2 (dashboard). Within a few seconds a new **Working** run appears in "Active sessions."

> "That label fired a **GitHub webhook**; the engine caught it and spun up a Devin session automatically — zero clicks in my own app. Notice the trigger source reads `webhook`, not manual."

**SCREEN:** Click the new run to open its drawer; let the **Activity log** stream for a beat.

> "And I can watch it reason in real time. I'll let this one work in the background while I walk you through a finished result and how it's built."

(Close the drawer. **Leave it running — do not wait on it.**)

## 3. Drill into a finished run (1:15–2:30)
**SCREEN:** Tab 2 (dashboard). In the runs table, click the **#28 (tests)** run to open its drawer. Stay on the default **Activity log** tab.

> "Here's a completed one. This Activity log is Devin's actual streamed work — it read the issue, explored the repo, wrote the tests, ran them, and opened the PR. It's not a black box."

**SCREEN:** Click the **Result** tab in the drawer.

> "Every session returns a **structured-output contract** — summary, files changed, verification, risk, confidence, and **estimated engineer-minutes saved**. That last field is how we put a number on value."

**SCREEN:** Click the **JSON** tab in the drawer.

> "And it's genuinely machine-readable — here's the raw JSON the engine consumes. The dashboard never scrapes text; it reads these fields directly, which is what makes the metrics trustworthy."

**SCREEN:** Click the **PR link** in the drawer → real PR diff opens on GitHub. Then back, and click the **Devin session link** → app.devin.ai session.

> "Real PR, real session — fully auditable. This is Devin, the product, doing the engineering; my system is the orchestration and the scoreboard around it."

## 4. ARCHITECTURE — the meat (2:30–3:45)
**SCREEN:** Switch to Tab 3 (ARCHITECTURE.md rendered) and scroll to the **End-to-end flow** diagram. Point at the boxes as you talk.

> "Quick tour of how it actually fits together. Follow the diagram: an engineer labels an issue, that webhook hits my orchestrator, the orchestrator starts a Devin session, Devin opens the PR, and a background poller folds the session and PR state into the dashboard. Four ideas drove the design.
>
> **First, the trigger is a plug-in, not the core.** A GitHub webhook hits exactly one endpoint, and that handler is the *only* GitHub-specific code in the system. The same internal path could just as easily be fired by a Snyk scan, a PagerDuty alert, or a nightly cron. Swapping the trigger doesn't touch the engine.
>
> **Second, the engine orchestrates — it doesn't write code.** When an event comes in, it creates a Devin session with a scoped prompt, the target repo, and a structured-output schema, then manages that session's lifecycle and collects the result. Devin does the engineering; my app conducts.
>
> **Third — and this is my favorite — it's near-stateless. There's no database.** Every session is tagged in Devin, and the structured output plus the PRs *are* the state. In fact, I restarted this process right before recording, and it rebuilt the entire dashboard just by listing Devin sessions by tag. Devin is the source of truth; my app is a disposable view on top of it.
>
> **Fourth, observability is built in, not bolted on.** Every run carries status, confidence, time-to-PR, ACUs, and minutes-saved — which sets up the numbers I'll show you in a second."

**SCREEN:** Quick glance — switch to Tab 2 (dashboard) and check the run you triggered in step 2; it should have progressed.

> "And there's the run I kicked off a few minutes ago — it's moved right along, completely on its own."

## 5. WHY Devin, not a script (3:45–4:10)
**SCREEN:** Tab 2 (dashboard), runs table / categories visible.

> "Worth saying why this is an autonomous agent and not a script. A bot can bump a version — it can't fix the breakage that bump causes, write the missing test, or reason about a CVE's blast radius. Devin does that open-ended work end to end. That's the difference between automating a keystroke and automating the *task*."

## 6. ROI — the numbers as the payoff (4:10–4:50)
**SCREEN:** Tab 2 (dashboard). NOW sweep the top KPI row left→right, then the cost/ACU stat strip. Point between "hours saved" and "cost/PR" on the money line.

> "Which brings us to the scoreboard — and this is the whole point. PRs opened, success rate, and the two numbers that matter to a budget: **hours of senior-engineer time saved**, against **cost per fix**. We're talking roughly **a dollar of compute per fix** versus 20–45 minutes of senior-engineer time — call it a 10–20× return, running unattended and in parallel. Every fix you saw earlier rolls up into exactly these numbers."

## 7. WHEN — next steps + close (4:50–5:00)
**SCREEN:** Tab 2 (dashboard), or webcam full.

> "From here: wire it to security scanners so new CVEs auto-open fix PRs, gate auto-merge on the confidence signal, and roll up per-team backlog burn-down. The thesis: treat Devin as a **fleet of autonomous engineers you orchestrate by events** — and measure it like one. Thanks."

---

### Reminders
- New arc: **problem first (on the issues page), numbers last (as ROI proof).** Don't open on the dashboard.
- The early trigger is the trick: start it in step 2, walk away, glance back in step 4 — feels alive, frees airtime.
- Linger on the **Activity log**, the **JSON** tab, and the **session links** — that's where Devin (the product) shines.
- Show the **ARCHITECTURE.md flow diagram** while narrating section 4.
- One continuous take; if you fumble, keep going.
- Land the cost-vs-hours line clearly in section 6 — that's the VP's takeaway.
