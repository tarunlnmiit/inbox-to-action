"""Mailbox providers: pluggable per-account fetch + draft (never send).

`build_accounts(settings)` turns config into a list of MailAccount objects
(Gmail / Google Workspace). Each account fetches its own unread mail and persists
drafts to its own mailbox — the agent stays account-agnostic.
"""

from inbox_to_action.mailboxes.base import (
    AccountConfig,
    MailAccount,
    build_accounts,
)

__all__ = ["AccountConfig", "MailAccount", "build_accounts"]
