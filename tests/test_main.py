from typer.testing import CliRunner

from inbox_to_action import main

runner = CliRunner()


def test_run_host_provider_errors(monkeypatch):
    monkeypatch.setenv("PROVIDER", "host")
    result = runner.invoke(main.app, ["run", "--mock"])
    assert result.exit_code == 1
    assert "host" in result.output.lower()


def test_run_missing_key_errors(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = runner.invoke(main.app, ["run", "--mock"])
    assert result.exit_code == 1
    assert "OPENROUTER_API_KEY" in result.output


def test_run_mock_end_to_end(monkeypatch, tmp_path):
    """Full --mock run with a stubbed reasoner (no network)."""
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    from conftest import FakeReasoner

    def router(messages, schema):
        if schema is None:
            return "reply text"
        props = schema.get("properties", {})
        if "category" in props:
            return {"category": "action_needed"}
        if "tasks" in props:
            return {"tasks": [{"text": "Send deck", "deadline": "Thu"}]}
        if "needs_calendar" in props:
            return {"needs_calendar": True, "reason": "call"}
        return {}

    monkeypatch.setattr(main, "get_reasoner", lambda provider: FakeReasoner(router))

    report_path = tmp_path / "triage-report.md"
    tasks_path = tmp_path / "tasks.md"
    result = runner.invoke(
        main.app,
        [
            "run",
            "--mock",
            "--report-path",
            str(report_path),
            "--tasks-path",
            str(tasks_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert report_path.exists()
    assert tasks_path.exists()
    assert "Send deck" in tasks_path.read_text()


def test_run_no_emails(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(main.gmail, "fetch_emails", lambda **kw: [])
    result = runner.invoke(main.app, ["run", "--mock"])
    assert result.exit_code == 0
    assert "No emails" in result.output


def test_run_fetch_failure(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    def boom(**kw):
        raise RuntimeError("gmail down")

    monkeypatch.setattr(main.gmail, "fetch_emails", boom)
    result = runner.invoke(main.app, ["run"])
    assert result.exit_code == 1
    assert "Fetch failed" in result.output
