import httpx
import respx

from inbox_to_action.models import Email, Task, TriageResult
from inbox_to_action.tools import notify


def _results():
    a = TriageResult(
        email=Email(id="1", sender="jobs@x.com", subject="Top Tech Roles", body="b"),
        category="action_needed",
        draft_id="r-123",
        tasks=[Task(text="Send Q3 deck", deadline="Thursday", source_email_id="1")],
    )
    b = TriageResult(
        email=Email(id="2", sender="no-reply@g.com", subject="Security alert", body="b"),
        category="action_needed",
        draft_note="no reply — automated sender",
    )
    c = TriageResult(
        email=Email(id="3", sender="n@x.com", subject="Weekly news", body="b"),
        category="newsletter",
    )
    return [a, b, c]


def test_format_summary_has_counts_actions_tasks_drafts():
    msg = notify.format_summary(_results())
    assert "3 emails" in msg and "2 action" in msg and "1 newsletter" in msg
    assert "Top Tech Roles — draft ready" in msg
    assert "Security alert — no draft (no reply — automated sender)" in msg
    assert "Send Q3 deck (Thursday)" in msg
    assert "1 draft(s) saved" in msg and "#drafts" in msg


def test_format_summary_no_drafts_mode():
    msg = notify.format_summary(_results(), no_drafts=True)
    assert "preview — no drafts created" in msg
    assert "saved →" not in msg


def test_format_summary_truncates_long_input():
    many = [
        TriageResult(
            email=Email(id=str(i), sender="a@b.com", subject="X" * 80, body="b"),
            category="action_needed",
            draft_id="r-1",
        )
        for i in range(300)
    ]
    msg = notify.format_summary(many)
    assert len(msg) <= notify._SAFE_LEN + 2 and msg.endswith("…")


def test_send_telegram_skips_when_unconfigured(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    def boom(*a, **k):  # must NOT be called
        raise AssertionError("no HTTP when unconfigured")

    monkeypatch.setattr(httpx, "post", boom)
    assert notify.send_telegram(_results()) is False


@respx.mock
def test_send_telegram_accepts_telegram_token_alias(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_TOKEN", "ALIAS9")  # autopilot-jobs env name
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    route = respx.post("https://api.telegram.org/botALIAS9/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    assert notify.send_telegram(_results()) is True
    assert route.called


def test_send_telegram_skips_on_empty_results(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    assert notify.send_telegram([]) is False


@respx.mock
def test_send_telegram_posts_when_configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOT123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "9988")
    route = respx.post("https://api.telegram.org/botBOT123/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    assert notify.send_telegram(_results()) is True
    assert route.called
    body = route.calls.last.request.content.decode()
    assert '"chat_id"' in body and "9988" in body and "Inbox triage" in body
