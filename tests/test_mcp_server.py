import json

import mcp_server


def test_fetch_emails_tool_returns_json():
    out = mcp_server.fetch_emails(mock=True)
    data = json.loads(out)
    assert len(data) == 5
    assert "sender" in data[0]


def test_save_gmail_draft_mock():
    # No Gmail token configured in test env -> mock-draft path.
    out = mcp_server.save_gmail_draft("to@x.com", "Re: Hi", "body")
    assert "mock-draft" in out


def test_append_tasks(tmp_path):
    path = tmp_path / "tasks.md"
    out = mcp_server.append_tasks(
        [{"text": "Do X", "deadline": "Fri"}, {"text": ""}], str(path)
    )
    assert "1 task" in out
    assert "Do X" in path.read_text()


def test_write_report(tmp_path):
    path = tmp_path / "r.md"
    out = mcp_server.write_report("# hi", str(path))
    assert path.read_text() == "# hi"
    assert str(path) in out
