from conftest import FakeReasoner
from inbox_to_action.config import Rule, Settings
from inbox_to_action.tools import classifier


def test_classify_returns_category(sample_email):
    r = FakeReasoner(lambda m, s: {"category": "action_needed"})
    assert classifier.classify_email(sample_email, r) == "action_needed"


def test_classify_accepts_bare_string(sample_email):
    # Weak provider (e.g. claude CLI ignoring --json-schema) returns a bare word.
    assert classifier.classify_email(sample_email, FakeReasoner(lambda m, s: "noise")) == "noise"
    assert classifier.classify_email(sample_email, FakeReasoner(lambda m, s: '"fyi"\n')) == "fyi"


def test_classify_unrecognized_defaults_fyi(sample_email):
    assert classifier.classify_email(sample_email, FakeReasoner(lambda m, s: "banana")) == "fyi"


def test_rule_short_circuits_llm(sample_email):
    """A matching rule returns its category WITHOUT calling the reasoner."""
    settings = Settings(
        rules=(Rule("sender", "example.com", "action_needed"),)
    )
    r = FakeReasoner(lambda m, s: {"category": "noise"})
    assert classifier.classify_email(sample_email, r, settings) == "action_needed"
    assert r.calls == []  # LLM never invoked


def test_no_matching_rule_falls_through_to_llm(sample_email):
    settings = Settings(rules=(Rule("sender", "nomatch.io", "noise"),))
    r = FakeReasoner(lambda m, s: {"category": "fyi"})
    assert classifier.classify_email(sample_email, r, settings) == "fyi"
    assert len(r.calls) == 1


def test_instructions_injected_into_system_prompt(sample_email):
    settings = Settings(triage_instructions="Treat job alerts as action_needed.")
    captured = {}

    def router(messages, schema):
        captured["system"] = messages[0]["content"]
        return {"category": "fyi"}

    classifier.classify_email(sample_email, FakeReasoner(router), settings)
    assert "Treat job alerts as action_needed." in captured["system"]
    assert "User triage preferences" in captured["system"]


def test_classify_invalid_falls_back_to_fyi(sample_email):
    r = FakeReasoner(lambda m, s: {"category": "totally_invalid"})
    assert classifier.classify_email(sample_email, r) == "fyi"


def test_classify_non_dict_falls_back(sample_email):
    r = FakeReasoner(lambda m, s: "oops")
    assert classifier.classify_email(sample_email, r) == "fyi"


def test_classify_sends_schema(sample_email):
    r = FakeReasoner(lambda m, s: {"category": "noise"})
    classifier.classify_email(sample_email, r)
    assert r.calls[0]["json_schema"]["properties"]["category"]["enum"]
