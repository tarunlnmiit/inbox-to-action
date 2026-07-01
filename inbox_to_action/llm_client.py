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
import shutil
import subprocess
from typing import Any, Optional

# OpenAI-compatible provider config: base_url + which env var holds the key.
_OPENAI_COMPAT = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "google/gemma-4-31b-it:free",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "nim": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NIM_API_KEY",
        "alt_key_env": "NVIDIA_API_KEY",  # accept the conventional NVIDIA name too
        "default_model": "meta/llama-3.3-70b-instruct",
    },
    "ollama": {
        "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "key_env": None,  # no key needed
        "default_model": "llama3.1",
    },
}

_ANTHROPIC_DEFAULT_MODEL = "claude-opus-4-8"

# OpenRouter free models rotate availability and get "rate-limited upstream"
# (429) often. We hand OpenRouter a fallback list so it auto-routes to the next
# available model, and retry transient 429/5xx with backoff. These are all
# verified-available free models (2026-06-30).
_OPENROUTER_FREE_FALLBACKS = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]
_RETRY_STATUS = {429, 502, 503}
_MAX_RETRIES = 4
_RETRY_BASE_SECONDS = 3.0
# Per-request HTTP timeout (seconds). Big models on long threads can be slow;
# generous by default, overridable via env.
_HTTP_TIMEOUT = float(os.environ.get("INBOX_TO_ACTION_HTTP_TIMEOUT", "150"))

# Keyless provider backed by the local `claude` CLI (Claude Code). Uses the
# user's existing login — no API key. Great for fast iteration.
_CLAUDE_PROVIDERS = {"claude", "claude_cli"}
_CLAUDE_TIMEOUT_SECONDS = 180


class LLMError(RuntimeError):
    """Raised on provider/config errors with a user-friendly message."""


def active_provider() -> str:
    return os.environ.get("PROVIDER", "openrouter").strip().lower()


def _resolve_key(cfg: dict) -> str:
    """Return the API key for an OpenAI-compat provider, honoring an alt env name."""
    for env_name in (cfg.get("key_env"), cfg.get("alt_key_env")):
        if env_name:
            val = os.environ.get(env_name, "").strip()
            if val:
                return val
    return ""


def _model(provider: str) -> str:
    env = os.environ.get("MODEL", "").strip()
    if env:
        return env
    if provider in _OPENAI_COMPAT:
        return _OPENAI_COMPAT[provider]["default_model"]
    if provider == "anthropic":
        return _ANTHROPIC_DEFAULT_MODEL
    if provider in _CLAUDE_PROVIDERS:
        return ""  # empty → let the claude CLI use its configured default
    raise LLMError(f"Unknown provider {provider!r}")


def validate_config(provider: Optional[str] = None) -> None:
    """Fail fast with a clear message if the selected provider is unusable."""
    provider = provider or active_provider()
    if provider == "host":
        return
    if provider in _OPENAI_COMPAT:
        cfg = _OPENAI_COMPAT[provider]
        key_env = cfg["key_env"]
        if key_env and not _resolve_key(cfg):
            names = " or ".join(n for n in (key_env, cfg.get("alt_key_env")) if n)
            raise LLMError(
                f"PROVIDER={provider} requires {names} to be set (see .env.example)."
            )
        return
    if provider == "anthropic":
        # Keyless is allowed (ant auth login). Nothing to validate up front;
        # the SDK resolves credentials at call time.
        return
    if provider in _CLAUDE_PROVIDERS:
        if shutil.which("claude") is None:
            raise LLMError(
                "PROVIDER=claude needs the `claude` CLI (Claude Code) on PATH."
            )
        return
    raise LLMError(
        f"Unknown PROVIDER={provider!r}. Use one of: "
        f"{', '.join(list(_OPENAI_COMPAT) + ['anthropic', 'claude', 'host'])}."
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
    if provider in _CLAUDE_PROVIDERS:
        return _complete_claude_cli(messages, json_schema=json_schema)
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
        headers["Authorization"] = f"Bearer {_resolve_key(cfg)}"

    primary = _model(provider)
    payload: dict[str, Any] = {
        "model": primary,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    # OpenRouter: supply a fallback model list so it auto-routes past a
    # throttled free model within a single request.
    if provider == "openrouter":
        fallbacks = [m for m in _OPENROUTER_FREE_FALLBACKS if m != primary]
        payload["models"] = [primary, *fallbacks]
    if json_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": json_schema, "strict": True},
        }

    url = f"{cfg['base_url']}/chat/completions"
    resp = _post_with_retry(httpx, url, headers, payload, provider)

    data = resp.json()
    choices = data.get("choices")
    if not choices:
        err = data.get("error") or data
        raise LLMError(f"{provider} returned no choices: {str(err)[:200]}")
    text = choices[0]["message"]["content"]
    if json_schema is not None:
        return _parse_json(text)
    return text


def _post_with_retry(httpx, url, headers, payload, provider):
    """POST with backoff on transient 429/5xx and network timeouts.

    Larger models (e.g. NIM llama-3.3-70b on long threads) can exceed a short
    read timeout; treat timeouts as retryable rather than failing the whole run.
    """
    import time

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=_HTTP_TIMEOUT)
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BASE_SECONDS * (2**attempt))
                continue
            raise LLMError(f"{provider} request timed out after retries: {e}") from e
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            last_exc = e
            if status in _RETRY_STATUS and attempt < _MAX_RETRIES:
                time.sleep(_retry_delay(e.response, attempt))
                continue
            raise LLMError(f"{provider} request failed: {e}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"{provider} request failed: {e}") from e
    raise LLMError(f"{provider} request failed: {last_exc}")  # pragma: no cover


def _retry_delay(response, attempt: int) -> float:
    """Honor Retry-After when present, else exponential backoff."""
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return _RETRY_BASE_SECONDS * (2**attempt)


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


def _complete_claude_cli(
    messages: list[dict[str, str]],
    *,
    json_schema: Optional[dict[str, Any]],
) -> Any:
    """Keyless completion via the local `claude` CLI (Claude Code, headless).

    Uses `--json-schema` for native structured output. No API key — relies on
    the user's existing Claude Code login.
    """
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    user = "\n\n".join(m["content"] for m in messages if m["role"] != "system")

    cmd = ["claude", "-p", user, "--output-format", "json"]
    if system:
        cmd += ["--append-system-prompt", system]
    if json_schema is not None:
        cmd += ["--json-schema", json.dumps(json_schema)]
    model = _model("claude")
    if model:
        cmd += ["--model", model]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_CLAUDE_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LLMError(f"claude CLI failed: {e}") from e
    if proc.returncode != 0:
        raise LLMError(
            f"claude CLI exited {proc.returncode}: {(proc.stderr or '')[:300]}"
        )

    text = _extract_claude_result(proc.stdout)
    if json_schema is not None:
        return _parse_json(text)
    return text


def _extract_claude_result(stdout: str) -> str:
    """Pull the `result` text from the claude CLI's JSON event output."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise LLMError(f"claude CLI returned non-JSON: {stdout[:200]!r}") from e
    events = data if isinstance(data, list) else [data]
    for el in events:
        if isinstance(el, dict) and el.get("type") == "result":
            if el.get("is_error"):
                raise LLMError(f"claude CLI error: {el.get('result')!r}")
            return el.get("result", "")
    raise LLMError("claude CLI output had no result element")


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
