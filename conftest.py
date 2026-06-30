"""Shared test fixtures. Presence at repo root puts top-level modules on sys.path."""

from __future__ import annotations

import pytest

from inbox_to_action.models import Email


@pytest.fixture(autouse=True)
def _isolate_gmail_token(monkeypatch, tmp_path):
    """Point the Gmail token at a nonexistent path so tests never touch a real
    cached token (which would flip create_draft from 'mock-draft' to live API)."""
    from inbox_to_action.tools import gmail

    monkeypatch.setattr(gmail, "_TOKEN_PATH", tmp_path / "no-token.json")


class FakeReasoner:
    """A scriptable Reasoner for tests.

    `router(messages, json_schema) -> value` decides each response. The default
    router produces sensible structured/text output keyed by the schema shape.
    """

    def __init__(self, router=None):
        self.router = router or _default_router
        self.calls: list[dict] = []

    def complete(self, messages, *, json_schema=None, max_tokens=1024):
        self.calls.append({"messages": messages, "json_schema": json_schema})
        return self.router(messages, json_schema)


def _default_router(messages, json_schema):
    if json_schema is None:
        return "Default generated text."
    props = json_schema.get("properties", {})
    if "category" in props:
        return {"category": "fyi"}
    if "tasks" in props:
        return {"tasks": []}
    if "needs_calendar" in props:
        return {"needs_calendar": False, "reason": None}
    return {}


@pytest.fixture
def fake_reasoner():
    return FakeReasoner()


@pytest.fixture
def sample_email():
    return Email(
        id="e1",
        sender="alice@example.com",
        subject="Please review the proposal",
        body="Can you review the attached proposal and send feedback by Friday?",
        thread_id="t1",
    )


@pytest.fixture
def long_email():
    return Email(
        id="e2",
        sender="bob@example.com",
        subject="Long update",
        body=" ".join(["word"] * 600),
        thread_id="t2",
    )
