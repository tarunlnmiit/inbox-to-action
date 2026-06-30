"""MCP server — lets Claude Code drive inbox-to-action keyless.

Claude Code is the LLM here, so this server exposes IO tools only. The host
fetches emails, reasons over them (classify / summarize / extract / draft) on
its own, then calls these tools to persist drafts, tasks, and the report. No
provider key is needed.

Run: `python -m inbox_to_action.mcp_server`  (or `inbox-to-action mcp`).
Register in Claude Code:
  `claude mcp add inbox-to-action -- python -m inbox_to_action.mcp_server`
This is also the Docker CMD that the Glama listing builds.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from inbox_to_action.tools import gmail, tasks as tasks_tool
from inbox_to_action.models import Task

mcp = FastMCP("inbox-to-action")


@mcp.tool()
def fetch_emails(since: str = "24h", mock: bool = True) -> str:
    """Fetch unread emails (JSON list). Use mock=True for the fixture demo.

    Returns a JSON array of {id, sender, subject, body, thread_id, received}.
    Reason over these yourself: classify each, summarize long ones, extract
    tasks and draft replies for action_needed items, then call the IO tools.
    """
    emails = gmail.fetch_emails(since=since, mock=mock)
    return json.dumps([asdict(e) for e in emails], indent=2)


@mcp.tool()
def save_gmail_draft(to: str, subject: str, body: str, thread_id: str = "") -> str:
    """Save a reply as a Gmail DRAFT (never sends). Returns the draft id."""
    draft_id = gmail.create_draft(to, subject, body, thread_id=thread_id)
    return f"Saved draft {draft_id} to {to}"


@mcp.tool()
def append_tasks(items: list[dict], path: str = "tasks.md") -> str:
    """Append tasks to tasks.md. Each item: {text, deadline?}."""
    task_objs = [
        Task(text=i["text"], deadline=i.get("deadline")) for i in items if i.get("text")
    ]
    out = tasks_tool.write_tasks_md(task_objs, path)
    return f"Wrote {len(task_objs)} task(s) to {out}"


@mcp.tool()
def write_report(markdown: str, path: str = "triage-report.md") -> str:
    """Write the final triage report markdown to disk."""
    Path(path).write_text(markdown, encoding="utf-8")
    return f"Wrote report to {path}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
