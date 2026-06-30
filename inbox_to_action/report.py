"""Render the final triage-report.md from a list of TriageResult."""

from __future__ import annotations

from pathlib import Path

from inbox_to_action.models import CATEGORIES, TriageResult

_TITLES = {
    "action_needed": "🔴 Action needed",
    "fyi": "🔵 FYI",
    "newsletter": "📰 Newsletters",
    "noise": "🔇 Noise",
}


def render_report(results: list[TriageResult]) -> str:
    lines: list[str] = ["# Inbox Triage Report", ""]
    lines.append(_summary_line(results))
    lines.append("")

    by_cat: dict[str, list[TriageResult]] = {c: [] for c in CATEGORIES}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    for cat in CATEGORIES:
        items = by_cat.get(cat, [])
        lines.append(f"## {_TITLES.get(cat, cat)} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_None._")
            lines.append("")
            continue
        for r in items:
            lines.extend(_render_item(r))
        lines.append("")

    lines.extend(_render_tasks_section(results))
    lines.extend(_render_calendar_section(results))
    return "\n".join(lines).rstrip() + "\n"


def _summary_line(results: list[TriageResult]) -> str:
    counts = {c: 0 for c in CATEGORIES}
    for r in results:
        counts[r.category] = counts.get(r.category, 0) + 1
    parts = [f"**{counts[c]}** {c}" for c in CATEGORIES]
    return f"{len(results)} emails · " + " · ".join(parts)


def _render_item(r: TriageResult) -> list[str]:
    out = [f"### {r.email.subject}", f"*from {r.email.sender}*", ""]
    if r.summary:
        out.append(f"> {r.summary}")
        out.append("")
    if r.draft_preview:
        out.append("**Drafted reply:**")
        out.append("")
        out.append("```")
        out.append(r.draft_preview.strip())
        out.append("```")
        status = (
            f"_saved as Gmail draft `{r.draft_id}`_"
            if r.draft_id and r.draft_id != "mock-draft"
            else "_draft preview (not saved — mock mode)_"
        )
        out.append(status)
        out.append("")
    if r.tasks:
        out.append("**Tasks:**")
        out.extend(t.to_markdown() for t in r.tasks)
        out.append("")
    if r.needs_calendar:
        out.append(f"📅 **Calendar:** {r.calendar_reason or 'needs a time block'}")
        out.append("")
    return out


def _render_tasks_section(results: list[TriageResult]) -> list[str]:
    all_tasks = [t for r in results for t in r.tasks]
    out = [f"## ✅ Tasks summary ({len(all_tasks)})", ""]
    if not all_tasks:
        out.append("_No tasks extracted._")
    else:
        out.extend(t.to_markdown() for t in all_tasks)
    out.append("")
    return out


def _render_calendar_section(results: list[TriageResult]) -> list[str]:
    flagged = [r for r in results if r.needs_calendar]
    out = [f"## 📅 Calendar blocks ({len(flagged)})", ""]
    if not flagged:
        out.append("_Nothing to schedule._")
    else:
        for r in flagged:
            out.append(
                f"- **{r.email.subject}** — {r.calendar_reason or 'time block'}"
            )
    out.append("")
    return out


def write_report(results: list[TriageResult], path: str | Path = "triage-report.md") -> Path:
    path = Path(path)
    path.write_text(render_report(results), encoding="utf-8")
    return path
