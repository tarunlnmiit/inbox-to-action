"""OutlookAccount — Microsoft Graph mailbox (personal outlook.com + M365).

Read + ReadWrite scopes only — NEVER send. Mirrors GmailAccount: one cached
token per account, drafts created via Graph `createReply` (a draft, never a
mail-send call). Requires the optional `msal` dependency:

    pip install 'inbox-to-action[outlook]'

Auth uses a user-supplied Azure public-client app (`client_id`); the delegated
permissions requested are `Mail.Read` + `Mail.ReadWrite` only.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import httpx

from inbox_to_action.models import Email
from inbox_to_action.tools import gmail as gmail_api

_GRAPH = "https://graph.microsoft.com/v1.0"

# Security invariant: read + draft-write only. NEVER Mail.Send.
SCOPES = ["Mail.Read", "Mail.ReadWrite"]

_HTTP_TIMEOUT = 30.0


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self._parts)).strip()


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    p = _TextExtractor()
    p.feed(html)
    return p.text()


def _token_cache_path(account_id: str) -> Path:
    return gmail_api._TOKEN_PATH.parent / "tokens" / f"{account_id}.msal.json"


class OutlookAccount:
    kind = "outlook"

    def __init__(
        self, id: str, label: str = "", client_id: str = "", tenant: str = "common"
    ):
        self.id = id
        self.label = label or id
        self._client_id = client_id
        self._tenant = tenant or "common"
        self._cache_path = _token_cache_path(id)
        self._app = None

    # --- auth -----------------------------------------------------------------
    def _msal_app(self):
        if self._app is None:
            import msal  # optional dep; imported lazily

            if not self._client_id:
                raise RuntimeError(
                    f"Outlook account '{self.id}' needs a `client_id` "
                    "(Azure public-client app) in config."
                )
            cache = msal.SerializableTokenCache()
            if self._cache_path.exists():
                cache.deserialize(self._cache_path.read_text(encoding="utf-8"))
            self._app = msal.PublicClientApplication(
                self._client_id,
                authority=f"https://login.microsoftonline.com/{self._tenant}",
                token_cache=cache,
            )
        return self._app

    def _persist_cache(self) -> None:
        app = self._app
        if app is not None and app.token_cache.has_state_changed:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(app.token_cache.serialize(), encoding="utf-8")

    def _token(self) -> str:
        app = self._msal_app()
        result = None
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if not result:
            result = app.acquire_token_interactive(SCOPES)
        self._persist_cache()
        if "access_token" not in result:
            raise RuntimeError(
                f"Outlook auth failed: {result.get('error_description', result)}"
            )
        return result["access_token"]

    def authorize(self) -> None:
        self._token()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token()}"}

    # --- fetch ----------------------------------------------------------------
    def fetch_emails(self, *, since: str = "24h", max_results: int = 50) -> list[Email]:
        params = {
            "$filter": "isRead eq false",
            "$top": str(max_results),
            "$select": "id,conversationId,subject,from,receivedDateTime,body,bodyPreview",
            "$orderby": "receivedDateTime desc",
        }
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.get(
                f"{_GRAPH}/me/mailFolders/inbox/messages",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
        emails: list[Email] = []
        for m in data.get("value", []):
            body = m.get("body", {}) or {}
            content = body.get("content", "")
            if (body.get("contentType") or "").lower() == "html":
                content = _html_to_text(content)
            sender = (
                ((m.get("from") or {}).get("emailAddress") or {}).get("address", "")
            )
            emails.append(
                Email(
                    id=str(m.get("id", "")),
                    sender=sender,
                    subject=m.get("subject", "") or "",
                    body=content or m.get("bodyPreview", "") or "",
                    thread_id=m.get("conversationId", "") or "",
                    received=m.get("receivedDateTime", "") or "",
                    account=self.id,
                )
            )
        return emails

    # --- draft (never send) ---------------------------------------------------
    def create_draft(
        self, to: str, subject: str, body: str, *, thread_id: str = "", mock: bool = False
    ) -> str:
        if mock:
            return "mock-outlook-draft"
        payload = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}] if to else [],
        }
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(
                f"{_GRAPH}/me/messages", headers=self._headers(), json=payload
            )
            resp.raise_for_status()
            return resp.json().get("id", "")

    def save_draft(self, email: Email, body: str, *, mock: bool = False) -> str:
        """Create a reply DRAFT to `email` via Graph createReply (never sends)."""
        if mock:
            return "mock-outlook-draft"
        headers = self._headers()
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            # createReply returns a draft message we then fill in.
            r = client.post(
                f"{_GRAPH}/me/messages/{email.id}/createReply", headers=headers
            )
            r.raise_for_status()
            draft_id = r.json().get("id", "")
            patch = client.patch(
                f"{_GRAPH}/me/messages/{draft_id}",
                headers=headers,
                json={"body": {"contentType": "Text", "content": body}},
            )
            patch.raise_for_status()
            return draft_id
