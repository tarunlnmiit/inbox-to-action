"""Shared data types for inbox-to-action.

Kept dependency-free so every other module (tools, agent, report, MCP server)
can import these without pulling in HTTP/Gmail/LLM packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Classification labels. Order matters for report rendering.
CATEGORIES = ("action_needed", "fyi", "newsletter", "noise")

# Threads longer than this (in words) get summarized.
SUMMARY_WORD_THRESHOLD = 500


@dataclass
class Email:
    """A single fetched email/thread."""

    id: str
    sender: str
    subject: str
    body: str
    thread_id: str = ""
    received: str = ""  # ISO timestamp

    def word_count(self) -> int:
        return len(self.body.split())

    @classmethod
    def from_dict(cls, d: dict) -> "Email":
        return cls(
            id=str(d["id"]),
            sender=d.get("sender", ""),
            subject=d.get("subject", ""),
            body=d.get("body", ""),
            thread_id=d.get("thread_id", str(d["id"])),
            received=d.get("received", ""),
        )


@dataclass
class Task:
    """A task extracted from an action_needed email."""

    text: str
    deadline: Optional[str] = None  # ISO date or human string, may be None
    source_email_id: str = ""

    def to_markdown(self) -> str:
        box = "- [ ] "
        line = f"{box}{self.text}"
        if self.deadline:
            line += f"  _(due {self.deadline})_"
        return line


@dataclass
class TriageResult:
    """Everything the agent produced for one email."""

    email: Email
    category: str
    summary: Optional[str] = None
    tasks: list[Task] = field(default_factory=list)
    draft_preview: Optional[str] = None
    draft_id: Optional[str] = None  # Gmail draft id, when saved
    needs_calendar: bool = False
    calendar_reason: Optional[str] = None
