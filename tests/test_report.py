import report
from models import Email, Task, TriageResult


def _result(**kw):
    email = kw.pop("email", Email(id="x", sender="s@e.com", subject="Subj", body="b"))
    return TriageResult(email=email, **kw)


def test_render_has_all_category_sections():
    out = report.render_report([_result(category="fyi")])
    for title in ("Action needed", "FYI", "Newsletters", "Noise"):
        assert title in out


def test_render_summary_line_counts():
    results = [
        _result(category="action_needed"),
        _result(category="noise"),
        _result(category="noise"),
    ]
    out = report.render_report(results)
    assert "3 emails" in out
    assert "**2** noise" in out


def test_render_includes_draft_and_tasks():
    r = _result(
        category="action_needed",
        draft_preview="Sure, sending it over.",
        draft_id="draft-9",
        tasks=[Task(text="Send deck", deadline="Thu")],
        needs_calendar=True,
        calendar_reason="kickoff call",
    )
    out = report.render_report([r])
    assert "Sure, sending it over." in out
    assert "draft-9" in out
    assert "Send deck" in out
    assert "kickoff call" in out


def test_render_mock_draft_marked_not_saved():
    r = _result(category="action_needed", draft_preview="hi", draft_id="mock-draft")
    out = report.render_report([r])
    assert "not saved" in out


def test_write_report(tmp_path):
    p = tmp_path / "triage-report.md"
    report.write_report([_result(category="fyi")], p)
    assert p.exists()
    assert p.read_text().startswith("# Inbox Triage Report")
