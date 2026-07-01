"""GmailAccount — one Gmail (personal or Workspace) mailbox.

Delegates to the low-level `tools.gmail` API layer (read + compose scopes only,
never send), giving each account its own cached token so multiple accounts can
be triaged in one run.
"""

from __future__ import annotations

from pathlib import Path

from inbox_to_action.models import Email
from inbox_to_action.tools import gmail as gmail_api


def _account_token_path(account_id: str) -> Path | None:
    """Per-account token path. `default` keeps the legacy single-account path
    (so existing tokens / env override keep working)."""
    if account_id == "default":
        return None  # tools.gmail falls back to its legacy _TOKEN_PATH
    return (
        gmail_api._TOKEN_PATH.parent / "tokens" / f"{account_id}.json"
    )


class GmailAccount:
    kind = "gmail"

    def __init__(self, id: str, label: str = "", client_secret: str | None = None):
        self.id = id
        self.label = label or id
        self._client_secret = client_secret
        self._token_path = _account_token_path(id)
        self._svc = None

    def _service(self):
        if self._svc is None:
            self._svc = gmail_api._service(
                token_path=self._token_path, client_secrets=self._client_secret
            )
        return self._svc

    def fetch_emails(self, *, since: str = "24h", max_results: int = 50) -> list[Email]:
        emails = gmail_api.fetch_emails(
            since=since, service=self._service(), max_results=max_results
        )
        for e in emails:
            e.account = self.id
        return emails

    def create_draft(
        self, to: str, subject: str, body: str, *, thread_id: str = "", mock: bool = False
    ) -> str:
        return gmail_api.create_draft(
            to, subject, body, thread_id=thread_id, service=self._service(), mock=mock
        )

    def save_draft(self, email: Email, body: str, *, mock: bool = False) -> str:
        return gmail_api.save_draft(
            email, body, service=self._service(), mock=mock
        )

    def authorize(self) -> None:
        gmail_api.get_credentials(
            client_secrets=self._client_secret, token_path=self._token_path
        )
