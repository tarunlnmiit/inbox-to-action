"""Agentic orchestration.

The model's own outputs drive which tools run per email (dynamic selection):
classification decides whether task-extraction, reply-drafting, and calendar
flagging fire — the pipeline is not hardcoded per email. `TOOL_SCHEMAS` exposes
the same tools as OpenAI/Anthropic function schemas (reused by the MCP server),
demonstrating the function-calling surface.
"""

from __future__ import annotations

from pathlib import Path

from typing import Optional

from inbox_to_action.config import Settings
from inbox_to_action.models import CATEGORIES, Email, TriageResult
from inbox_to_action.reasoner import Reasoner
from inbox_to_action.tools import calendar_flag, classifier, gmail, summarizer, tasks

# Function-calling schemas for the agent's tool surface (also used by MCP).
TOOL_SCHEMAS = [
    {
        "name": "classify_email",
        "description": "Classify an email into action_needed | fyi | newsletter | noise.",
        "parameters": {
            "type": "object",
            "properties": {"email_id": {"type": "string"}},
            "required": ["email_id"],
        },
    },
    {
        "name": "summarize_thread",
        "description": "Summarize a long thread (>500 words) into two lines.",
        "parameters": {
            "type": "object",
            "properties": {"email_id": {"type": "string"}},
            "required": ["email_id"],
        },
    },
    {
        "name": "extract_tasks",
        "description": "Extract action items with deadlines from an email.",
        "parameters": {
            "type": "object",
            "properties": {"email_id": {"type": "string"}},
            "required": ["email_id"],
        },
    },
    {
        "name": "draft_reply",
        "description": "Draft a reply and save it as a Gmail draft (never sends).",
        "parameters": {
            "type": "object",
            "properties": {"email_id": {"type": "string"}},
            "required": ["email_id"],
        },
    },
    {
        "name": "flag_for_calendar",
        "description": "Flag an email that needs a calendar block.",
        "parameters": {
            "type": "object",
            "properties": {"email_id": {"type": "string"}},
            "required": ["email_id"],
        },
    },
]


def triage_email(
    email: Email,
    reasoner: Reasoner,
    *,
    gmail_service=None,
    save_drafts: bool = True,
    no_drafts: bool = False,
    mock: bool = False,
    settings: Optional[Settings] = None,
    accounts: Optional[dict] = None,
) -> TriageResult:
    """Run the per-email agentic trajectory. Model decides the path.

    `no_drafts` = classify/summarize/extract only; never compose or write a draft
    (safe preview). Automated/no-reply senders are also skipped for drafting.
    """
    category = classifier.classify_email(email, reasoner, settings)
    result = TriageResult(email=email, category=category)

    # Summarize long threads regardless of category.
    result.summary = summarizer.summarize_thread(email, reasoner)

    if category == "action_needed":
        result.tasks = tasks.extract_tasks(email, reasoner)

        if no_drafts:
            result.draft_note = "preview mode — no draft created"
        elif gmail.is_noreply(email.sender):
            result.draft_note = "no reply — automated sender"
        else:
            reply_text = gmail.compose_reply(email, reasoner)
            result.draft_preview = reply_text
            if save_drafts and reply_text:
                account = accounts.get(email.account) if accounts else None
                if account is not None:
                    result.draft_id = account.save_draft(email, reply_text, mock=mock)
                else:
                    # Legacy single-account path (also used by tests).
                    result.draft_id = gmail.save_draft(
                        email, reply_text, service=gmail_service, mock=mock
                    )

        needs_cal, reason = calendar_flag.flag_for_calendar(email, reasoner)
        result.needs_calendar = needs_cal
        result.calendar_reason = reason

    return result


def run_agent(
    emails: list[Email],
    reasoner: Reasoner,
    *,
    gmail_service=None,
    save_drafts: bool = True,
    no_drafts: bool = False,
    write_tasks: bool = True,
    tasks_path: str | Path = "tasks.md",
    todoist: bool = False,
    on_progress=None,
    mock: bool = False,
    settings: Optional[Settings] = None,
    accounts: Optional[dict] = None,
) -> list[TriageResult]:
    """Triage every email and persist extracted tasks."""
    results: list[TriageResult] = []
    for i, email in enumerate(emails, 1):
        if on_progress:
            on_progress(i, len(emails), email)
        results.append(
            triage_email(
                email,
                reasoner,
                gmail_service=gmail_service,
                save_drafts=save_drafts,
                no_drafts=no_drafts,
                mock=mock,
                settings=settings,
                accounts=accounts,
            )
        )

    all_tasks = [t for r in results for t in r.tasks]
    if write_tasks and all_tasks:
        tasks.write_tasks_md(all_tasks, tasks_path)
    if todoist and all_tasks:
        tasks.push_todoist(all_tasks)

    return results


def category_counts(results: list[TriageResult]) -> dict[str, int]:
    counts = {c: 0 for c in CATEGORIES}
    for r in results:
        counts[r.category] = counts.get(r.category, 0) + 1
    return counts
