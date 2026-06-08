"""Prompt construction and the structured-output contract for remediation sessions.

The engine only has the issue text + event payload at runtime. Repo-specific
conventions (run pre-commit, prefer unit tests, `Closes #N`, keep scope tight)
belong in a reusable Playbook passed via `playbook_id` -- but we also restate the
essentials here so the system works without one.
"""
from __future__ import annotations

# JSON Schema (Draft 7) for the machine-readable handoff every session must return.
STRUCTURED_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "pr_url": {
            "type": "string",
            "description": "URL of the opened pull request. Empty string if no PR was opened.",
        },
        "summary": {
            "type": "string",
            "description": "One- or two-sentence summary of what was changed and why.",
        },
        "issue_type": {
            "type": "string",
            "enum": [
                "security",
                "dependency",
                "deprecation",
                "tests",
                "documentation",
                "code_quality",
                "other",
            ],
            "description": "Self-classified category of the work performed.",
        },
        "files_changed": {
            "type": "integer",
            "description": "Number of files modified.",
        },
        "key_changes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short bullet list of the most important changes.",
        },
        "tests_passed": {
            "type": "boolean",
            "description": "Whether the relevant test suite / pre-commit checks passed locally.",
        },
        "verification": {
            "type": "string",
            "description": "How the change was verified (e.g. 'ran pytest tests/unit, 53 passed; pre-commit clean').",
        },
        "risk_level": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Reviewer-facing risk of the change.",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Agent confidence in the correctness/completeness of the fix.",
        },
        "estimated_human_minutes": {
            "type": "integer",
            "description": "Your honest estimate of how many minutes a competent human engineer would need to complete this task end-to-end.",
        },
        "blockers": {
            "type": "string",
            "description": "If the task could not be completed, explain the blocker. Empty string otherwise.",
        },
    },
    "required": ["summary", "issue_type", "confidence", "estimated_human_minutes"],
}


def build_prompt(repo: str, issue_number: int, issue_title: str, issue_body: str) -> str:
    body = (issue_body or "").strip() or "(no description provided)"
    return f"""You are an autonomous software-maintenance engineer working on the GitHub repository `{repo}`.

Resolve GitHub issue #{issue_number}: "{issue_title}"
https://github.com/{repo}/issues/{issue_number}

--- ISSUE DESCRIPTION ---
{body}
-------------------------

How to work:
1. Implement a complete, correct fix scoped strictly to what this issue asks. Do NOT make unrelated changes.
2. Follow the repository's contributing conventions. This repo has an `AGENTS.md` (and CONTRIBUTING docs) -- read and follow them. In particular: run `pre-commit run --all-files` (ruff, black, mypy, pylint) and prefer unit tests over integration tests.
3. Verify your work: run the relevant tests and the pre-commit hooks, and make them pass BEFORE opening a PR.
4. Open a pull request against the default branch (`master`) whose body contains `Closes #{issue_number}`. Keep the PR focused on this one issue.
5. If you cannot safely and correctly complete the task (ambiguous, no fix available, or too risky), do NOT force a low-quality PR. Stop and explain the blocker in your structured output.

When you finish, call `provide_structured_output` (with `is_final=true`) populating the required schema. Be honest in `confidence`, `risk_level`, and `estimated_human_minutes`.
"""
