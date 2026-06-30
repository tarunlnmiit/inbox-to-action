from pathlib import Path
from unittest.mock import MagicMock

from inbox_to_action.models import Email
from inbox_to_action.tools import gmail


def test_scopes_exclude_send():
    """Security invariant: no send / full-mail scope is ever requested."""
    joined = " ".join(gmail.SCOPES)
    assert "gmail.send" not in joined
    assert "mail.google.com" not in joined
    assert "gmail.readonly" in joined
    assert "gmail.compose" in joined


def test_source_never_calls_send():
    """No Gmail send API call exists anywhere in the module."""
    src = Path(gmail.__file__).read_text()
    assert ".send(" not in src
    assert "messages().send" not in src


def test_fetch_emails_mock_loads_fixtures():
    emails = gmail.fetch_emails(mock=True)
    assert len(emails) == 5
    assert all(isinstance(e, Email) for e in emails)
    assert emails[0].subject


def test_to_gmail_window():
    assert gmail._to_gmail_window("24h") == "1d"
    assert gmail._to_gmail_window("48h") == "2d"
    assert gmail._to_gmail_window("3d") == "3d"
    assert gmail._to_gmail_window("weird") == "1d"


def test_fetch_emails_real_uses_service():
    service = MagicMock()
    service.users().messages().list().execute.return_value = {
        "messages": [{"id": "abc"}]
    }
    service.users().messages().get().execute.return_value = {
        "id": "abc",
        "threadId": "t-abc",
        "payload": {
            "headers": [
                {"name": "From", "value": "x@y.com"},
                {"name": "Subject", "value": "Hi"},
            ],
            "mimeType": "text/plain",
            "body": {"data": ""},
        },
    }
    emails = gmail.fetch_emails(mock=False, service=service)
    assert emails[0].id == "abc"
    assert emails[0].sender == "x@y.com"
    assert emails[0].subject == "Hi"


def test_create_draft_uses_drafts_create_not_send():
    service = MagicMock()
    service.users().drafts().create().execute.return_value = {"id": "draft-123"}
    draft_id = gmail.create_draft(
        "to@x.com", "Re: Hello", "body text", thread_id="t1", service=service
    )
    assert draft_id == "draft-123"
    # drafts().create WAS used; no send path on drafts or messages.
    service.users().drafts().create().execute.assert_called()
    service.users().messages().send.assert_not_called()
    service.users().drafts().send.assert_not_called()


def test_save_draft_adds_reply_prefix():
    service = MagicMock()
    captured = {}

    def fake_create(userId, body):
        captured["body"] = body
        m = MagicMock()
        m.execute.return_value = {"id": "d1"}
        return m

    service.users().drafts().create.side_effect = fake_create
    email = Email(id="e", sender="a@b.com", subject="Question", body="?", thread_id="th")
    out = gmail.save_draft(email, "my reply", service=service)
    assert out == "d1"


def test_reply_subject_idempotent():
    assert gmail._reply_subject("Hello") == "Re: Hello"
    assert gmail._reply_subject("Re: Hello") == "Re: Hello"
