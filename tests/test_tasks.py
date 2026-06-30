import httpx
import respx

from conftest import FakeReasoner
from models import Task
from tools import tasks


def test_extract_tasks_parses(sample_email):
    r = FakeReasoner(
        lambda m, s: {
            "tasks": [
                {"text": "Review proposal", "deadline": "Friday"},
                {"text": "", "deadline": None},  # dropped (empty text)
            ]
        }
    )
    out = tasks.extract_tasks(sample_email, r)
    assert len(out) == 1
    assert out[0].text == "Review proposal"
    assert out[0].deadline == "Friday"
    assert out[0].source_email_id == sample_email.id


def test_extract_tasks_non_dict(sample_email):
    r = FakeReasoner(lambda m, s: "nope")
    assert tasks.extract_tasks(sample_email, r) == []


def test_write_tasks_md_creates_and_appends(tmp_path):
    path = tmp_path / "tasks.md"
    tasks.write_tasks_md([Task(text="First", deadline="Mon")], path)
    assert path.exists()
    content = path.read_text()
    assert "- [ ] First" in content
    assert "due Mon" in content

    tasks.write_tasks_md([Task(text="Second")], path)
    content = path.read_text()
    assert "First" in content and "Second" in content
    assert content.count("# Tasks") == 1  # header not duplicated


def test_write_tasks_md_empty_noop(tmp_path):
    path = tmp_path / "tasks.md"
    tasks.write_tasks_md([], path)
    # no tasks -> still creates header-only file, no checklist lines
    assert "- [ ]" not in path.read_text()


def test_push_todoist_no_token_returns_zero():
    assert tasks.push_todoist([Task(text="x")], token=None) == 0


@respx.mock
def test_push_todoist_creates(monkeypatch):
    route = respx.post("https://api.todoist.com/rest/v2/tasks").mock(
        return_value=httpx.Response(200, json={"id": "1"})
    )
    n = tasks.push_todoist(
        [Task(text="Do it", deadline="tomorrow")], token="tok"
    )
    assert n == 1
    assert route.called
    sent = route.calls[0].request
    assert b"due_string" in sent.content
