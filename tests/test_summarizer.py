from conftest import FakeReasoner
from tools import summarizer


def test_needs_summary_threshold(sample_email, long_email):
    assert not summarizer.needs_summary(sample_email)
    assert summarizer.needs_summary(long_email)


def test_short_email_not_summarized(sample_email):
    r = FakeReasoner(lambda m, s: "should not be called")
    assert summarizer.summarize_thread(sample_email, r) is None
    assert r.calls == []  # reasoner not invoked for short email


def test_long_email_summarized(long_email):
    r = FakeReasoner(lambda m, s: "  Two line summary.  ")
    assert summarizer.summarize_thread(long_email, r) == "Two line summary."
    assert len(r.calls) == 1
