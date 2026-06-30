"""Pluggable reasoning core.

LLM-dependent tools (classify / summarize / extract / draft / calendar) don't
call the provider directly — they receive a `complete` callable. This is the
seam that lets the same tool code run in two modes:

* `ProviderReasoner` — wires in `llm_client.complete` (standalone CLI).
* `HostReasoner` — has no LLM; raises `HostReasoningRequired`. Used when Claude
  Code is the model (MCP / Skill), so reasoning is supplied by the host and the
  tool surface is IO-only.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol


class HostReasoningRequired(RuntimeError):
    """Raised when a reasoning step is attempted under the host reasoner."""


class Reasoner(Protocol):
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: Optional[dict[str, Any]] = None,
        max_tokens: int = 1024,
    ) -> Any: ...


class ProviderReasoner:
    """Reasoner backed by the configured LLM provider."""

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: Optional[dict[str, Any]] = None,
        max_tokens: int = 1024,
    ) -> Any:
        from inbox_to_action import llm_client

        return llm_client.complete(
            messages, json_schema=json_schema, max_tokens=max_tokens
        )


class HostReasoner:
    """No-LLM reasoner; the host (Claude Code) does the thinking."""

    def complete(self, *args: Any, **kwargs: Any) -> Any:
        raise HostReasoningRequired(
            "No LLM in host mode. Claude Code supplies reasoning via the MCP "
            "server or the /inbox-to-action skill."
        )


def get_reasoner(provider: str) -> Reasoner:
    return HostReasoner() if provider == "host" else ProviderReasoner()
