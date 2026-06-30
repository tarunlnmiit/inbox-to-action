import json

from inbox_to_action import config
from inbox_to_action.config import Rule, Settings, load_settings, match_rule


def _write(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_load_missing_file_returns_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("TRIAGE_INSTRUCTIONS", raising=False)
    monkeypatch.delenv("INBOX_TO_ACTION_CONFIG", raising=False)
    s = load_settings(tmp_path / "nope.json")
    assert s == Settings()
    assert s.triage_instructions == "" and s.rules == ()


def test_load_file(monkeypatch, tmp_path):
    monkeypatch.delenv("TRIAGE_INSTRUCTIONS", raising=False)
    p = _write(
        tmp_path,
        {
            "triage_instructions": "I'm job hunting.",
            "rules": [
                {"field": "sender", "contains": "hirist", "category": "action_needed"}
            ],
        },
    )
    s = load_settings(p)
    assert s.triage_instructions == "I'm job hunting."
    assert s.rules == (Rule("sender", "hirist", "action_needed"),)


def test_env_overrides_instructions(monkeypatch, tmp_path):
    p = _write(tmp_path, {"triage_instructions": "from file"})
    monkeypatch.setenv("TRIAGE_INSTRUCTIONS", "from env")
    assert load_settings(p).triage_instructions == "from env"


def test_invalid_rules_dropped(monkeypatch, tmp_path):
    monkeypatch.delenv("TRIAGE_INSTRUCTIONS", raising=False)
    p = _write(
        tmp_path,
        {
            "rules": [
                {"field": "sender", "contains": "ok", "category": "noise"},
                {"field": "bogus", "contains": "x", "category": "noise"},  # bad field
                {"field": "sender", "contains": "y", "category": "invalid"},  # bad cat
                {"field": "sender", "contains": "", "category": "noise"},  # empty
                "not-a-dict",
            ]
        },
    )
    s = load_settings(p)
    assert s.rules == (Rule("sender", "ok", "noise"),)


def test_bad_json_falls_back(monkeypatch, tmp_path):
    monkeypatch.delenv("TRIAGE_INSTRUCTIONS", raising=False)
    p = tmp_path / "config.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert load_settings(p) == Settings()


def test_env_config_path(monkeypatch, tmp_path):
    monkeypatch.delenv("TRIAGE_INSTRUCTIONS", raising=False)
    p = _write(tmp_path, {"triage_instructions": "via env path"})
    monkeypatch.setenv("INBOX_TO_ACTION_CONFIG", str(p))
    assert load_settings().triage_instructions == "via env path"


def test_match_rule_precedence_and_fields():
    rules = (
        Rule("subject", "invoice", "noise"),
        Rule("sender", "hirist", "action_needed"),
        Rule("any", "unsubscribe", "newsletter"),
    )
    assert match_rule("hirist.tech", "Your invoice", "body", rules) == "noise"  # first wins
    assert match_rule("hirist.tech", "New role", "body", rules) == "action_needed"
    assert match_rule("a@b.com", "hi", "click unsubscribe here", rules) == "newsletter"
    assert match_rule("a@b.com", "hi", "nothing", rules) is None


def test_match_rule_case_insensitive():
    rules = (Rule("sender", "HIRIST", "action_needed"),)
    assert match_rule("info@hirist.tech", "x", "y", rules) == "action_needed"
