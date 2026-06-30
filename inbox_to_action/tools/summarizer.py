"""summarize_thread tool — condense long threads to ~2 lines."""

from __future__ import annotations

from typing import Optional

from inbox_to_action.models import SUMMARY_WORD_THRESHOLD, Email
from inbox_to_action.reasoner import Reasoner

_SYSTEM = (
    "Summarize the email below in at most two short lines. "
    "Capture who wants what and any deadline. No preamble."
)


def needs_summary(email: Email) -> bool:
    return email.word_count() > SUMMARY_WORD_THRESHOLD


def summarize_thread(email: Email, reasoner: Reasoner) -> Optional[str]:
    """Summarize only if the thread exceeds the word threshold; else None."""
    if not needs_summary(email):
        return None
    user = f"Subject: {email.subject}\n\n{email.body[:8000]}"
    text = reasoner.complete(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        max_tokens=200,
    )
    return text.strip() if isinstance(text, str) else None
