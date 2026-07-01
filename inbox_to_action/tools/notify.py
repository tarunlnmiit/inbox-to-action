"""Telegram summary notification.

Outbound push of the already-produced triage summary to a Telegram chat. Mirrors
the `push_todoist` pattern: env-configured, silent skip when unset, opt-in flag.
NEVER sends email — this only notifies. Plain-text message (no markdown parse_mode)
so emoji / `*` / `_` in subjects can't trigger a Telegram 400.
"""

from __future__ import annotations

import os

from inbox_to_action.models import CATEGORIES, TriageResult

_DRAFTS_URL = "https://mail.google.com/mail/u/0/#drafts"
_TELEGRAM_MAX = 4096
_SAFE_LEN = 3900  # leave headroom under the hard cap


def _counts(results: list[TriageResult]) -> dict[str, int]:
    counts = {c: 0 for c in CATEGORIES}
    for r in results:
        counts[r.category] = counts.get(r.category, 0) + 1
    return counts


def format_summary(results: list[TriageResult], *, no_drafts: bool = False) -> str:
    """Build the concise plain-text summary sent to Telegram."""
    counts = _counts(results)
    lines: list[str] = [
        f"📥 Inbox triage — {len(results)} emails · "
        f"{counts['action_needed']} action, {counts['fyi']} fyi, "
        f"{counts['newsletter']} newsletter, {counts['noise']} noise",
    ]

    actions = [r for r in results if r.category == "action_needed"]
    if actions:
        lines.append("")
        lines.append("🔴 Action needed")
        for r in actions:
            if r.draft_id and r.draft_id != "mock-draft":
                mark = " — draft ready"
            elif r.draft_note:
                mark = f" — no draft ({r.draft_note})"
            else:
                mark = ""
            lines.append(f"• {r.email.subject}{mark}")

    all_tasks = [t for r in results for t in r.tasks]
    if all_tasks:
        lines.append("")
        lines.append("✅ Tasks")
        for t in all_tasks:
            due = f" ({t.deadline})" if t.deadline else ""
            lines.append(f"• {t.text}{due}")

    saved = sum(1 for r in results if r.draft_id and r.draft_id != "mock-draft")
    lines.append("")
    if no_drafts:
        lines.append("preview — no drafts created")
    elif saved:
        lines.append(f"{saved} draft(s) saved → {_DRAFTS_URL}")
    else:
        lines.append("no drafts created")

    text = "\n".join(lines)
    if len(text) > _SAFE_LEN:
        text = text[:_SAFE_LEN].rstrip() + "\n…"
    return text


def send_telegram(
    results: list[TriageResult],
    *,
    token: str | None = None,
    chat_id: str | None = None,
    no_drafts: bool = False,
) -> bool:
    """Send the summary to Telegram. Returns True if sent, False if skipped.

    Skips silently (no HTTP) when the bot token / chat id is missing or there are
    no results — same contract as `push_todoist`.
    """
    # TELEGRAM_TOKEN is accepted as an alias (autopilot-jobs uses that name).
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id or not results:
        return False

    import httpx

    resp = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": format_summary(results, no_drafts=no_drafts),
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return True
