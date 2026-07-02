"""OutlookAccount tests: never-send invariant, mock zero-writes, Graph mapping."""

from pathlib import Path

import httpx
import respx

from inbox_to_action.mailboxes.outlook import OutlookAccount, _html_to_text
from inbox_to_action.models import Email

_GRAPH = "https://graph.microsoft.com/v1.0"


def _account(monkeypatch, tmp_path):
    acc = OutlookAccount(id="ol", label="Outlook", client_id="app-123")
    acc._cache_path = Path(tmp_path) / "ol.msal.json"
    monkeypatch.setattr(acc, "_token", lambda: "fake-token")
    return acc


def test_scopes_exclude_send():
    from inbox_to_action.mailboxes import outlook

    joined = " ".join(outlook.SCOPES).lower()
    assert "mail.send" not in joined
    assert "send" not in joined
    assert "mail.read" in joined
    assert "mail.readwrite" in joined


def test_source_never_sends():
    from inbox_to_action.mailboxes import outlook

    src = Path(outlook.__file__).read_text()
    assert "sendMail" not in src
    assert "/send" not in src


def test_html_to_text_strips_tags():
    assert _html_to_text("<p>Hello <b>world</b></p>") == "Hello world"
    assert _html_to_text("") == ""


@respx.mock
def test_create_draft_mock_makes_no_http(monkeypatch, tmp_path):
    acc = _account(monkeypatch, tmp_path)
    out = acc.create_draft("a@b.com", "Sub", "Body", mock=True)
    assert out == "mock-outlook-draft"
    assert len(respx.calls) == 0  # zero real writes in mock mode


@respx.mock
def test_save_draft_mock_makes_no_http(monkeypatch, tmp_path):
    acc = _account(monkeypatch, tmp_path)
    email = Email(id="m1", sender="x@y.com", subject="Hi", body="…")
    out = acc.save_draft(email, "reply", mock=True)
    assert out == "mock-outlook-draft"
    assert len(respx.calls) == 0


@respx.mock
def test_fetch_maps_graph_json(monkeypatch, tmp_path):
    acc = _account(monkeypatch, tmp_path)
    respx.get(f"{_GRAPH}/me/mailFolders/inbox/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "AAA",
                        "conversationId": "conv-1",
                        "subject": "Need review",
                        "from": {"emailAddress": {"address": "boss@corp.com"}},
                        "receivedDateTime": "2026-07-01T10:00:00Z",
                        "body": {"contentType": "html", "content": "<p>Please <b>reply</b></p>"},
                        "bodyPreview": "Please reply",
                    }
                ]
            },
        )
    )
    emails = acc.fetch_emails(since="7d", max_results=10)
    assert len(emails) == 1
    e = emails[0]
    assert e.id == "AAA"
    assert e.sender == "boss@corp.com"
    assert e.subject == "Need review"
    assert e.body == "Please reply"  # HTML stripped
    assert e.thread_id == "conv-1"
    assert e.account == "ol"


@respx.mock
def test_save_draft_uses_createreply_not_send(monkeypatch, tmp_path):
    acc = _account(monkeypatch, tmp_path)
    reply = respx.post(f"{_GRAPH}/me/messages/m1/createReply").mock(
        return_value=httpx.Response(201, json={"id": "draft-9"})
    )
    patch = respx.patch(f"{_GRAPH}/me/messages/draft-9").mock(
        return_value=httpx.Response(200, json={"id": "draft-9"})
    )
    send_route = respx.post(f"{_GRAPH}/me/sendMail").mock(
        return_value=httpx.Response(202)
    )
    email = Email(id="m1", sender="x@y.com", subject="Hi", body="…")
    out = acc.save_draft(email, "my reply")
    assert out == "draft-9"
    assert reply.called
    assert patch.called
    assert not send_route.called  # never sends
