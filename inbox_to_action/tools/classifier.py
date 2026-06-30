"""classify_email tool — sort each email into one of four buckets."""

from __future__ import annotations

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


def classify_email(email: Email, reasoner: Reasoner) -> str:
    """Return one of CATEGORIES. Falls back to 'fyi' on an unexpected value."""
    user = f"From: {email.sender}\nSubject: {email.subject}\n\n{email.body[:4000]}"
    result = reasoner.complete(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        json_schema=_SCHEMA,
        max_tokens=64,
    )
    category = result.get("category", "fyi") if isinstance(result, dict) else "fyi"
    return category if category in CATEGORIES else "fyi"
