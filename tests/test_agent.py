from inbox_to_action import agent
from conftest import FakeReasoner
from inbox_to_action.models import Email


def _router(messages, json_schema):
    """Action-needed email that yields a task, a draft, and a calendar flag."""
    if json_schema is None:
        return "Drafted reply body."
    props = json_schema.get("properties", {})
    if "category" in props:
        return {"category": "action_needed"}
    if "tasks" in props:
        return {"tasks": [{"text": "Do the thing", "deadline": "Friday"}]}
    if "needs_calendar" in props:
        return {"needs_calendar": True, "reason": "schedule a call"}
    return {}


def test_triage_action_needed_full_trajectory(sample_email):
    r = FakeReasoner(_router)
    result = agent.triage_email(sample_email, r, save_drafts=True)
    assert result.category == "action_needed"
    assert result.tasks and result.tasks[0].text == "Do the thing"
    assert result.draft_preview == "Drafted reply body."
    assert result.draft_id == "mock-draft"  # no Gmail configured
    assert result.needs_calendar is True
    assert result.calendar_reason == "schedule a call"


def test_triage_routes_draft_to_account(sample_email):
    """When an accounts map is given, the draft is saved via the email's account."""
    sample_email.account = "personal"
    calls = {}

    class FakeAccount:
        def save_draft(self, email, body, *, mock=False):
            calls["email_id"] = email.id
            calls["mock"] = mock
            return "acct-draft-1"

    result = agent.triage_email(
        sample_email,
        FakeReasoner(_router),
        save_drafts=True,
        accounts={"personal": FakeAccount()},
    )
    assert result.draft_id == "acct-draft-1"
    assert calls["email_id"] == sample_email.id


def test_triage_fyi_skips_action_tools(sample_email):
    r = FakeReasoner(lambda m, s: {"category": "fyi"} if s and "category" in s.get("properties", {}) else None)
    result = agent.triage_email(sample_email, r)
    assert result.category == "fyi"
    assert result.tasks == []
    assert result.draft_preview is None
    assert result.needs_calendar is False


def test_triage_summarizes_long_email(long_email):
    def router(messages, schema):
        if schema is None:
            return "Short summary."
        if "category" in schema.get("properties", {}):
            return {"category": "fyi"}
        return {}

    result = agent.triage_email(long_email, FakeReasoner(router))
    assert result.summary == "Short summary."


def test_run_agent_writes_tasks(tmp_path):
    emails = [Email(id="e1", sender="a@b.com", subject="s", body="b")]
    tasks_path = tmp_path / "tasks.md"
    results = agent.run_agent(
        emails, FakeReasoner(_router), save_drafts=True, tasks_path=tasks_path
    )
    assert len(results) == 1
    assert tasks_path.exists()
    assert "Do the thing" in tasks_path.read_text()


def test_run_agent_progress_callback(tmp_path):
    emails = [Email(id="e1", sender="a@b.com", subject="s", body="b")]
    seen = []
    agent.run_agent(
        emails,
        FakeReasoner(lambda m, s: {"category": "noise"} if s else "t"),
        tasks_path=tmp_path / "t.md",
        on_progress=lambda i, total, e: seen.append((i, total)),
    )
    assert seen == [(1, 1)]


def test_category_counts():
    from inbox_to_action.models import TriageResult

    results = [
        TriageResult(email=Email(id="1", sender="", subject="", body=""), category="fyi"),
        TriageResult(email=Email(id="2", sender="", subject="", body=""), category="fyi"),
    ]
    counts = agent.category_counts(results)
    assert counts["fyi"] == 2
    assert counts["noise"] == 0


def test_tool_schemas_present():
    names = {t["name"] for t in agent.TOOL_SCHEMAS}
    assert {
        "classify_email",
        "summarize_thread",
        "extract_tasks",
        "draft_reply",
        "flag_for_calendar",
    } <= names
