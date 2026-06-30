from conftest import FakeReasoner
from tools import classifier


def test_classify_returns_category(sample_email):
    r = FakeReasoner(lambda m, s: {"category": "action_needed"})
    assert classifier.classify_email(sample_email, r) == "action_needed"


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
