"""classify_email tool — sort each email into one of four buckets."""

from __future__ import annotations

from typing import Optional

from inbox_to_action.config import Settings, match_rule
from inbox_to_action.models import CATEGORIES, Email
from inbox_to_action.reasoner import Reasoner

_SCHEMA = {
    "type": "object",
    "properties": {"category": {"type": "string", "enum": list(CATEGORIES)}},
    "required": ["category"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You triage email. Classify each message into exactly one category:\n"
    "- action_needed: the recipient must reply or do something.\n"
    "- fyi: informational, no action required.\n"
    "- newsletter: marketing, digests, automated mailing lists.\n"
    "- noise: spam, receipts, notifications safe to ignore.\n"
    "Respond with the category only."
)


def classify_email(
    email: Email, reasoner: Reasoner, settings: Optional[Settings] = None
) -> str:
    """Return one of CATEGORIES. Falls back to 'fyi' on an unexpected value.

    Deterministic user rules (settings.rules) are applied first and short-circuit
    the LLM; otherwise the model classifies, guided by settings.triage_instructions.
    """
    if settings and settings.rules:
        forced = match_rule(email.sender, email.subject, email.body, settings.rules)
        if forced is not None:
            return forced

    system = _SYSTEM
    if settings and settings.triage_instructions:
        system = (
            f"{_SYSTEM}\n\nUser triage preferences (follow these closely):\n"
            f"{settings.triage_instructions}"
        )

    user = f"From: {email.sender}\nSubject: {email.subject}\n\n{email.body[:4000]}"
    result = reasoner.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        json_schema=_SCHEMA,
        max_tokens=64,
    )
    # Strong providers return {"category": ...}; weak ones (e.g. a claude CLI
    # that ignores --json-schema) may reply with a bare word like `noise` or a
    # short sentence. Accept both, default to fyi on anything unrecognized.
    if isinstance(result, dict):
        raw = str(result.get("category", "") or "")
    elif isinstance(result, str):
        raw = result
    else:
        raw = ""
    raw = raw.strip().strip("\"'").lower()
    if raw in CATEGORIES:
        return raw
    return next((c for c in CATEGORIES if c in raw), "fyi")
