"""flag_for_calendar tool — decide whether an email implies a meeting/time block."""

from __future__ import annotations

from inbox_to_action.models import Email
from inbox_to_action.reasoner import Reasoner

_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_calendar": {"type": "boolean"},
        "reason": {"type": ["string", "null"]},
    },
    "required": ["needs_calendar", "reason"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Decide if this email requires the recipient to block calendar time "
    "(a meeting request, a call to schedule, a deadline needing focused work). "
    "Give a short reason when true."
)


def flag_for_calendar(email: Email, reasoner: Reasoner) -> tuple[bool, str | None]:
    user = f"Subject: {email.subject}\n\n{email.body[:4000]}"
    result = reasoner.complete(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        json_schema=_SCHEMA,
        max_tokens=128,
    )
    if not isinstance(result, dict):
        return False, None
    needs = bool(result.get("needs_calendar"))
    reason = result.get("reason") or None
    return needs, (reason if needs else None)
