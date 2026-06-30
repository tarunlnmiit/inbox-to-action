"""extract_tasks tool + tasks.md writer + optional Todoist push."""

from __future__ import annotations

import os
from pathlib import Path

from models import Email, Task
from reasoner import Reasoner

_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "deadline": {"type": ["string", "null"]},
                },
                "required": ["text", "deadline"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["tasks"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Extract concrete action items the recipient must do, with deadlines if "
    "stated. Return an empty list if there are none. Keep each task one line. "
    "Use null for deadline when none is given."
)


def extract_tasks(email: Email, reasoner: Reasoner) -> list[Task]:
    user = f"Subject: {email.subject}\n\n{email.body[:6000]}"
    result = reasoner.complete(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        json_schema=_SCHEMA,
        max_tokens=512,
    )
    raw = result.get("tasks", []) if isinstance(result, dict) else []
    tasks: list[Task] = []
    for item in raw:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        tasks.append(
            Task(
                text=text,
                deadline=item.get("deadline") or None,
                source_email_id=email.id,
            )
        )
    return tasks


def write_tasks_md(tasks: list[Task], path: str | Path = "tasks.md") -> Path:
    """Append tasks to a local Markdown checklist. Creates the file if needed."""
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if not existing:
        existing = "# Tasks\n\n_Extracted by inbox-to-action._\n\n"
    lines = [t.to_markdown() for t in tasks]
    body = existing.rstrip() + "\n" + "\n".join(lines) + "\n" if lines else existing
    path.write_text(body, encoding="utf-8")
    return path


def push_todoist(tasks: list[Task], token: str | None = None) -> int:
    """Create tasks in Todoist (REST v2). Returns count created.

    Free tier. Skips silently (returns 0) when no token is configured.
    """
    token = token or os.environ.get("TODOIST_API_TOKEN")
    if not token or not tasks:
        return 0
    import httpx

    created = 0
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for t in tasks:
        payload: dict = {"content": t.text}
        if t.deadline:
            payload["due_string"] = t.deadline
        resp = httpx.post(
            "https://api.todoist.com/rest/v2/tasks",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        created += 1
    return created
