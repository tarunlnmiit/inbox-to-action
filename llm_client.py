"""Pluggable LLM provider layer.

One entry point — `complete()` — backed by a provider selected via the
`PROVIDER` env var. OpenRouter / Ollama / NIM / OpenAI share a single
OpenAI-compatible HTTP path; Anthropic uses the official `anthropic` SDK
(keyless via `ant auth login` when no key is set). `host` is a no-op provider
used when Claude Code supplies the reasoning (MCP / Skill mode).

`complete(messages, json_schema=...)` returns plain text, or a parsed dict when
a JSON schema is supplied (structured output).
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

# OpenAI-compatible provider config: base_url + which env var holds the key.
_OPENAI_COMPAT = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "meta-llama/llama-3.1-8b-instruct:free",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "nim": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NIM_API_KEY",
        "default_model": "meta/llama-3.1-8b-instruct",
    },
    "ollama": {
        "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "key_env": None,  # no key needed
        "default_model": "llama3.1",
    },
}

_ANTHROPIC_DEFAULT_MODEL = "claude-opus-4-8"


class LLMError(RuntimeError):
    """Raised on provider/config errors with a user-friendly message."""


def active_provider() -> str:
    return os.environ.get("PROVIDER", "openrouter").strip().lower()


def _model(provider: str) -> str:
    env = os.environ.get("MODEL", "").strip()
    if env:
        return env
    if provider in _OPENAI_COMPAT:
        return _OPENAI_COMPAT[provider]["default_model"]
    if provider == "anthropic":
        return _ANTHROPIC_DEFAULT_MODEL
    raise LLMError(f"Unknown provider {provider!r}")


def validate_config(provider: Optional[str] = None) -> None:
    """Fail fast with a clear message if the selected provider is unusable."""
    provider = provider or active_provider()
    if provider == "host":
        return
    if provider in _OPENAI_COMPAT:
        cfg = _OPENAI_COMPAT[provider]
        key_env = cfg["key_env"]
        if key_env and not os.environ.get(key_env):
            raise LLMError(
                f"PROVIDER={provider} requires {key_env} to be set "
                f"(see .env.example)."
            )
        return
    if provider == "anthropic":
        # Keyless is allowed (ant auth login). Nothing to validate up front;
        # the SDK resolves credentials at call time.
        return
    raise LLMError(
        f"Unknown PROVIDER={provider!r}. Use one of: "
        f"{', '.join(list(_OPENAI_COMPAT) + ['anthropic', 'host'])}."
    )


def complete(
    messages: list[dict[str, str]],
    *,
    json_schema: Optional[dict[str, Any]] = None,
    max_tokens: int = 1024,
) -> Any:
    """Run a chat completion.

    Returns a str, or a parsed dict when `json_schema` is given.
    Raises LLMError on misconfiguration or `host` provider (which has no LLM).
    """
    provider = active_provider()
    if provider == "host":
        raise LLMError(
            "PROVIDER=host has no LLM. Reasoning is supplied by Claude Code "
            "(use the MCP server or the /inbox-to-action skill)."
        )
    validate_config(provider)
    if provider in _OPENAI_COMPAT:
        return _complete_openai_compat(
            provider, messages, json_schema=json_schema, max_tokens=max_tokens
        )
    if provider == "anthropic":
        return _complete_anthropic(
            messages, json_schema=json_schema, max_tokens=max_tokens
        )
    raise LLMError(f"Unknown provider {provider!r}")


def _complete_openai_compat(
    provider: str,
    messages: list[dict[str, str]],
    *,
    json_schema: Optional[dict[str, Any]],
    max_tokens: int,
) -> Any:
    import httpx

    cfg = _OPENAI_COMPAT[provider]
    headers = {"Content-Type": "application/json"}
    if cfg["key_env"]:
        key = os.environ.get(cfg["key_env"], "")
        headers["Authorization"] = f"Bearer {key}"

    payload: dict[str, Any] = {
        "model": _model(provider),
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if json_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": json_schema, "strict": True},
        }

    url = f"{cfg['base_url']}/chat/completions"
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise LLMError(f"{provider} request failed: {e}") from e

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    if json_schema is not None:
        return _parse_json(text)
    return text


def _complete_anthropic(
    messages: list[dict[str, str]],
    *,
    json_schema: Optional[dict[str, Any]],
    max_tokens: int,
) -> Any:
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover - import guard
        raise LLMError(
            "PROVIDER=anthropic requires the `anthropic` package "
            "(pip install anthropic)."
        ) from e

    # Zero-arg client: resolves ANTHROPIC_API_KEY, then the `ant auth login`
    # OAuth profile — so this works keyless.
    client = anthropic.Anthropic()

    # Anthropic takes system separately from the message list.
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    convo = [m for m in messages if m["role"] != "system"]

    kwargs: dict[str, Any] = {
        "model": _model("anthropic"),
        "max_tokens": max_tokens,
        "messages": convo,
        # Adaptive thinking is the supported mode on Opus 4.8 (no budget_tokens).
        "thinking": {"type": "adaptive"},
    }
    if system:
        kwargs["system"] = system
    if json_schema is not None:
        kwargs["output_config"] = {
            "format": {"type": "json_schema", "schema": json_schema}
        }

    try:
        resp = client.messages.create(**kwargs)
    except Exception as e:  # anthropic raises various subclasses
        raise LLMError(f"anthropic request failed: {e}") from e

    text = "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )
    if json_schema is not None:
        return _parse_json(text)
    return text


def _parse_json(text: str) -> dict:
    """Parse JSON, tolerating ```json fences some models emit."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model did not return valid JSON: {text[:200]!r}") from e
