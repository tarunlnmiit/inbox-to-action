
from inbox_to_action.config import Settings, load_settings
from inbox_to_action.mailboxes import build_accounts
from inbox_to_action.mailboxes.base import AccountConfig, _coerce_accounts
from inbox_to_action.mailboxes.gmail import GmailAccount, _account_token_path
from inbox_to_action.models import Email


def test_build_accounts_default_is_single_gmail():
    accounts = build_accounts(Settings())
    assert len(accounts) == 1
    assert accounts[0].id == "default" and accounts[0].kind == "gmail"


def test_build_accounts_multi_gmail():
    settings = Settings(
        accounts=(
            AccountConfig(id="personal", kind="gmail", label="Personal"),
            AccountConfig(id="side", kind="gmail", label="Side"),
        )
    )
    accounts = build_accounts(settings)
    assert [a.id for a in accounts] == ["personal", "side"]
    assert all(a.kind == "gmail" for a in accounts)


def test_default_account_uses_legacy_token_path():
    assert _account_token_path("default") is None  # legacy single-account path
    p = _account_token_path("work")
    assert p is not None and p.name == "work.json" and p.parent.name == "tokens"


def test_coerce_accounts_drops_malformed():
    raw = [
        {"id": "ok", "kind": "gmail", "label": "OK"},
        {"id": "", "kind": "gmail"},  # no id
        {"id": "x", "kind": "imap"},  # bad kind
        "nope",
    ]
    out = _coerce_accounts(raw)
    assert len(out) == 1 and out[0].id == "ok" and out[0].kind == "gmail"


def test_load_settings_parses_accounts(monkeypatch, tmp_path):
    monkeypatch.delenv("TRIAGE_INSTRUCTIONS", raising=False)
    p = tmp_path / "config.json"
    p.write_text(
        '{"accounts": [{"id": "personal", "kind": "gmail", "label": "Me"}]}',
        encoding="utf-8",
    )
    s = load_settings(p)
    assert len(s.accounts) == 1 and s.accounts[0].label == "Me"


def test_gmail_account_tags_fetched_emails(monkeypatch):
    acc = GmailAccount(id="personal", label="Personal")
    monkeypatch.setattr(acc, "_service", lambda: object())
    from inbox_to_action.tools import gmail as gmail_api

    monkeypatch.setattr(
        gmail_api,
        "fetch_emails",
        lambda **kw: [Email(id="1", sender="a@b.com", subject="s", body="b")],
    )
    got = acc.fetch_emails(since="24h")
    assert got[0].account == "personal"  # tagged with the account id


def test_gmail_account_save_draft_delegates(monkeypatch):
    acc = GmailAccount(id="personal")
    monkeypatch.setattr(acc, "_service", lambda: "SVC")
    from inbox_to_action.tools import gmail as gmail_api

    captured = {}

    def fake_save(email, body, *, service=None, mock=False):
        captured.update(service=service, mock=mock)
        return "draft-9"

    monkeypatch.setattr(gmail_api, "save_draft", fake_save)
    out = acc.save_draft(Email(id="1", sender="a", subject="s", body="b"), "reply", mock=True)
    assert out == "draft-9"
    assert captured == {"service": "SVC", "mock": True}


def test_outlook_account_builds():
    settings = Settings(accounts=(AccountConfig(id="work", kind="outlook", client_id="x"),))
    accounts = build_accounts(settings)
    assert len(accounts) == 1
    assert accounts[0].kind == "outlook"
    assert accounts[0].id == "work"
