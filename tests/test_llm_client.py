import sys
import types

import httpx
import pytest
import respx

from inbox_to_action import llm_client


def test_active_provider_default(monkeypatch):
    monkeypatch.delenv("PROVIDER", raising=False)
    assert llm_client.active_provider() == "openrouter"


def test_validate_config_missing_key(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(llm_client.LLMError):
        llm_client.validate_config()


def test_validate_config_ollama_needs_no_key(monkeypatch):
    monkeypatch.setenv("PROVIDER", "ollama")
    llm_client.validate_config()  # should not raise


def test_validate_config_host_ok(monkeypatch):
    monkeypatch.setenv("PROVIDER", "host")
    llm_client.validate_config()


def test_validate_config_unknown(monkeypatch):
    monkeypatch.setenv("PROVIDER", "bogus")
    with pytest.raises(llm_client.LLMError):
        llm_client.validate_config()


def test_complete_host_raises(monkeypatch):
    monkeypatch.setenv("PROVIDER", "host")
    with pytest.raises(llm_client.LLMError):
        llm_client.complete([{"role": "user", "content": "hi"}])


@respx.mock
def test_complete_openai_compat_text(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "hello world"}}]}
        )
    )
    out = llm_client.complete([{"role": "user", "content": "hi"}])
    assert out == "hello world"
    assert route.called


@respx.mock
def test_complete_openai_compat_no_choices_raises(monkeypatch):
    # Rate-limited upstream sometimes returns HTTP 200 with an error body (no "choices")
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"error": {"message": "rate-limited upstream", "code": 429}}
        )
    )
    with pytest.raises(llm_client.LLMError, match="no choices"):
        llm_client.complete([{"role": "user", "content": "hi"}])


@respx.mock
def test_complete_openai_compat_json_schema(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"category": "fyi"}'}}]},
        )
    )
    schema = {"type": "object", "properties": {"category": {"type": "string"}}}
    out = llm_client.complete(
        [{"role": "user", "content": "x"}], json_schema=schema
    )
    assert out == {"category": "fyi"}


@respx.mock
def test_complete_openai_compat_non_json_degrades(monkeypatch):
    # Weak OpenAI-compat model ignores response_format and returns a bare token /
    # prose. Must NOT crash — _parse_json degrades (salvage, else raw string) so
    # the same graceful path applies to openrouter/nim/openai, not just claude.
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    schema = {"type": "object", "properties": {"category": {"type": "string"}}}
    for content, expected in [
        ("noise", "noise"),  # bare token → raw string (classifier coerces it)
        ("sure: {\"category\": \"fyi\"}", {"category": "fyi"}),  # salvaged
    ]:
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            return_value=httpx.Response(
                200, json={"choices": [{"message": {"content": content}}]}
            )
        )
        out = llm_client.complete([{"role": "user", "content": "x"}], json_schema=schema)
        assert out == expected


@respx.mock
def test_complete_http_error(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    with pytest.raises(llm_client.LLMError):
        llm_client.complete([{"role": "user", "content": "x"}])


@respx.mock
def test_openrouter_sends_fallback_models(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )
    )
    llm_client.complete([{"role": "user", "content": "hi"}])
    import json as _json

    body = _json.loads(route.calls[0].request.content)
    assert body["model"] == "google/gemma-4-31b-it:free"
    assert len(body["models"]) >= 2  # primary + fallbacks
    assert body["model"] == body["models"][0]


@respx.mock
def test_retry_on_429_then_success(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr("time.sleep", lambda *_: None)  # no real backoff
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate-limited"}),
            httpx.Response(429, json={"error": "rate-limited"}),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    assert llm_client.complete([{"role": "user", "content": "hi"}]) == "ok"


@respx.mock
def test_retry_exhausts_then_raises(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr("time.sleep", lambda *_: None)
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": "rate-limited"})
    )
    with pytest.raises(llm_client.LLMError):
        llm_client.complete([{"role": "user", "content": "hi"}])


def test_nim_accepts_nvidia_api_key_alias(monkeypatch):
    monkeypatch.setenv("PROVIDER", "nim")
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-xyz")
    llm_client.validate_config()  # must not raise
    cfg = llm_client._OPENAI_COMPAT["nim"]
    assert llm_client._resolve_key(cfg) == "nvapi-xyz"


def test_nim_missing_key_message_mentions_both(monkeypatch):
    monkeypatch.setenv("PROVIDER", "nim")
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(llm_client.LLMError) as ei:
        llm_client.validate_config()
    assert "NIM_API_KEY" in str(ei.value) and "NVIDIA_API_KEY" in str(ei.value)


@respx.mock
def test_retry_on_timeout_then_success(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr("time.sleep", lambda *_: None)
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=[
            httpx.ReadTimeout("slow"),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    assert llm_client.complete([{"role": "user", "content": "hi"}]) == "ok"


def test_retry_delay_honors_retry_after():
    resp = httpx.Response(429, headers={"retry-after": "7"})
    assert llm_client._retry_delay(resp, 0) == 7.0


def test_retry_delay_exponential_default():
    resp = httpx.Response(429)
    assert llm_client._retry_delay(resp, 0) == llm_client._RETRY_BASE_SECONDS
    assert llm_client._retry_delay(resp, 1) == llm_client._RETRY_BASE_SECONDS * 2


def test_parse_json_with_fences():
    assert llm_client._parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_salvages_embedded_object():
    assert llm_client._parse_json('sure: {"a": 1} done') == {"a": 1}
    assert llm_client._parse_json('[{"t": 1}] extra') == [{"t": 1}]


def test_parse_json_degrades_to_raw_string():
    # Weak providers may emit a bare token; don't crash — return it for coercion.
    assert llm_client._parse_json("noise") == "noise"
    assert llm_client._parse_json("not json") == "not json"


def test_complete_anthropic_keyless(monkeypatch):
    """Anthropic path uses the SDK with a zero-arg (keyless) client."""
    monkeypatch.setenv("PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    captured = {}

    class FakeBlock:
        type = "text"
        text = '{"category": "action_needed"}'

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(content=[FakeBlock()])

    class FakeAnthropic:
        def __init__(self, *a, **k):
            captured["init_args"] = (a, k)

        messages = FakeMessages()

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    schema = {"type": "object", "properties": {"category": {"type": "string"}}}
    out = llm_client.complete(
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        json_schema=schema,
    )
    assert out == {"category": "action_needed"}
    # zero-arg client (keyless) and adaptive thinking, no budget_tokens
    assert captured["init_args"] == ((), {})
    assert captured["thinking"] == {"type": "adaptive"}
    assert "budget_tokens" not in str(captured)
    assert captured["system"] == "sys"


# ── claude CLI provider (keyless) ───────────────────────────────────────────
def _claude_envelope(result: str, is_error: bool = False) -> str:
    """Mimic `claude -p --output-format json` event-array output."""
    import json as _json

    return _json.dumps(
        [
            {"type": "system", "subtype": "init"},
            {"type": "result", "is_error": is_error, "result": result},
        ]
    )


def _fake_run(captured, stdout="", returncode=0, stderr=""):
    def run(cmd, *a, **k):
        captured["cmd"] = cmd
        return types.SimpleNamespace(
            stdout=stdout, stderr=stderr, returncode=returncode
        )

    return run


def test_validate_claude_requires_cli(monkeypatch):
    monkeypatch.setenv("PROVIDER", "claude")
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: None)
    with pytest.raises(llm_client.LLMError):
        llm_client.validate_config()
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: "/usr/bin/claude")
    llm_client.validate_config()  # ok


def test_complete_claude_text(monkeypatch):
    monkeypatch.setenv("PROVIDER", "claude")
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: "/usr/bin/claude")
    cap = {}
    monkeypatch.setattr(
        llm_client.subprocess, "run", _fake_run(cap, stdout=_claude_envelope("PONG"))
    )
    out = llm_client.complete([{"role": "user", "content": "ping"}])
    assert out == "PONG"
    assert cap["cmd"][:2] == ["claude", "-p"]
    assert "--output-format" in cap["cmd"] and "json" in cap["cmd"]
    assert "--json-schema" not in cap["cmd"]  # text mode
    assert "--model" not in cap["cmd"]  # MODEL unset → use CLI default


def test_complete_claude_schema(monkeypatch):
    monkeypatch.setenv("PROVIDER", "claude")
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: "/usr/bin/claude")
    cap = {}
    monkeypatch.setattr(
        llm_client.subprocess,
        "run",
        _fake_run(cap, stdout=_claude_envelope('{"category":"action_needed"}')),
    )
    schema = {"type": "object", "properties": {"category": {"type": "string"}}}
    out = llm_client.complete(
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        json_schema=schema,
    )
    assert out == {"category": "action_needed"}
    assert "--json-schema" in cap["cmd"]
    assert "--append-system-prompt" in cap["cmd"]


def _seq_run(calls, stdouts):
    """Fake subprocess.run returning stdouts[i] on the i-th call; records cmds."""
    seq = iter(stdouts)

    def run(cmd, *a, **k):
        calls.append(cmd)
        return types.SimpleNamespace(stdout=next(seq), stderr="", returncode=0)

    return run


def test_complete_claude_schema_empty_result_falls_back(monkeypatch):
    # CLI version ignores --json-schema → empty result; fallback (no schema flag,
    # schema embedded in prompt) returns valid JSON.
    monkeypatch.setenv("PROVIDER", "claude")
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: "/usr/bin/claude")
    calls: list = []
    monkeypatch.setattr(
        llm_client.subprocess,
        "run",
        _seq_run(calls, [_claude_envelope(""), _claude_envelope('{"category":"fyi"}')]),
    )
    schema = {"type": "object", "properties": {"category": {"type": "string"}}}
    out = llm_client.complete(
        [{"role": "user", "content": "hi"}], json_schema=schema
    )
    assert out == {"category": "fyi"}
    assert "--json-schema" in calls[0]  # first attempt used the flag
    assert "--json-schema" not in calls[1]  # fallback embeds schema in prompt
    assert "schema" in calls[1][2].lower()  # -p <prompt> mentions the schema


def test_complete_claude_schema_empty_both_raises(monkeypatch):
    monkeypatch.setenv("PROVIDER", "claude")
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(
        llm_client.subprocess,
        "run",
        _seq_run([], [_claude_envelope(""), _claude_envelope("")]),
    )
    schema = {"type": "object", "properties": {"category": {"type": "string"}}}
    with pytest.raises(llm_client.LLMError, match="empty output"):
        llm_client.complete([{"role": "user", "content": "hi"}], json_schema=schema)


def test_complete_claude_nonzero_exit(monkeypatch):
    monkeypatch.setenv("PROVIDER", "claude")
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(
        llm_client.subprocess,
        "run",
        _fake_run({}, returncode=1, stderr="boom"),
    )
    with pytest.raises(llm_client.LLMError):
        llm_client.complete([{"role": "user", "content": "x"}])


def test_complete_claude_error_result(monkeypatch):
    monkeypatch.setenv("PROVIDER", "claude")
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(
        llm_client.subprocess,
        "run",
        _fake_run({}, stdout=_claude_envelope("rate limited", is_error=True)),
    )
    with pytest.raises(llm_client.LLMError):
        llm_client.complete([{"role": "user", "content": "x"}])


def test_complete_claude_model_override(monkeypatch):
    monkeypatch.setenv("PROVIDER", "claude")
    monkeypatch.setenv("MODEL", "claude-sonnet-4-6")
    monkeypatch.setattr(llm_client.shutil, "which", lambda _: "/usr/bin/claude")
    cap = {}
    monkeypatch.setattr(
        llm_client.subprocess, "run", _fake_run(cap, stdout=_claude_envelope("ok"))
    )
    llm_client.complete([{"role": "user", "content": "x"}])
    assert "--model" in cap["cmd"]
    assert "claude-sonnet-4-6" in cap["cmd"]
