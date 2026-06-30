"""extract_tasks tool + tasks.md writer + optional Todoist push."""

from __future__ import annotations

import os
from pathlib import Path

from inbox_to_action.models import Email, Task
from inbox_to_action.reasoner import Reasoner

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
    "Extract concrete action items the recipient must do. "
    "For each task: 'text' is one imperative line; 'deadline' is ONLY a short "
    "date or time phrase exactly as stated (e.g. 'Thursday', 'by Friday', "
    "'2026-07-01'), or null when none is given. Never put explanations, names, "
    "or the word 'null' inside the deadline string. Return an empty list if "
    "there are no action items."
)

# Deadline strings longer than this are almost certainly the model leaking
# commentary into the field; we drop them rather than render garbage.
_MAX_DEADLINE_LEN = 40


def _clean_deadline(value) -> str | None:
    """Keep only a short, sensible deadline phrase; else return None."""
    if not isinstance(value, str):
        return None
    # Take the first clause; small models sometimes append commentary.
    d = value.split(",")[0].split("(")[0].strip().strip(".")
    if not d or d.lower() == "null" or len(d) > _MAX_DEADLINE_LEN:
        return None
    return d


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
                deadline=_clean_deadline(item.get("deadline")),
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
