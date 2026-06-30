import sys
import types

import httpx
import pytest
import respx

import llm_client


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


def test_retry_delay_honors_retry_after():
    resp = httpx.Response(429, headers={"retry-after": "7"})
    assert llm_client._retry_delay(resp, 0) == 7.0


def test_retry_delay_exponential_default():
    resp = httpx.Response(429)
    assert llm_client._retry_delay(resp, 0) == llm_client._RETRY_BASE_SECONDS
    assert llm_client._retry_delay(resp, 1) == llm_client._RETRY_BASE_SECONDS * 2


def test_parse_json_with_fences():
    assert llm_client._parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_invalid():
    with pytest.raises(llm_client.LLMError):
        llm_client._parse_json("not json")


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
