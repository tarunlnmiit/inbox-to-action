"""Gmail tools — fetch_emails, compose_reply, save_draft.

Scopes are intentionally limited to READ + COMPOSE. There is no send scope and
no send call anywhere in this module — drafts only. (Enforced by tests.)
"""

from __future__ import annotations

import base64
import json
import os
from email.message import EmailMessage
from pathlib import Path

from inbox_to_action.models import Email
from inbox_to_action.reasoner import Reasoner

# READ + COMPOSE only. `gmail.compose` can create drafts but CANNOT send.
# Do not add gmail.send or the broad mail.google.com scope.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

_TOKEN_PATH = Path(
    os.environ.get(
        "INBOX_TO_ACTION_TOKEN",
        str(Path.home() / ".config" / "inbox-to-action" / "token.json"),
    )
)

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample_inbox.json"

_REPLY_SYSTEM = (
    "Draft a concise, professional reply to the email below from the "
    "recipient's perspective. Address the sender's request directly. "
    "No subject line, no signature block — just the body."
)


# ── Auth ────────────────────────────────────────────────────────────────────
def get_credentials(client_secrets: str | None = None):
    """Load cached creds, refreshing or running the install-app flow as needed."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        secrets = client_secrets or os.environ.get(
            "GMAIL_CLIENT_SECRETS", "client_secret.json"
        )
        flow = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES)
        creds = flow.run_local_server(port=0)
    _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _service(service=None):
    """Build the Gmail API client (or return an injected one for tests)."""
    if service is not None:
        return service
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=get_credentials())


# ── Fetch ───────────────────────────────────────────────────────────────────
def fetch_emails(
    *, since: str = "24h", mock: bool = False, service=None, max_results: int = 50
) -> list[Email]:
    """Fetch unread emails from the last `since` window.

    `--mock` loads fixtures so the demo runs with zero Gmail setup.
    """
    if mock:
        data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        return [Email.from_dict(d) for d in data]

    svc = _service(service)
    query = f"is:unread newer_than:{_to_gmail_window(since)}"
    listing = (
        svc.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    emails: list[Email] = []
    for ref in listing.get("messages", []):
        msg = (
            svc.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        emails.append(_parse_message(msg))
    return emails


def _to_gmail_window(since: str) -> str:
    """Map '24h' / '3d' to Gmail's newer_than syntax ('1d' / '3d')."""
    s = since.strip().lower()
    if s.endswith("h") and s[:-1].isdigit():
        hours = int(s[:-1])
        days = max(1, (hours + 23) // 24)
        return f"{days}d"
    if s.endswith("d") and s[:-1].isdigit():
        return s
    return "1d"


def _parse_message(msg: dict) -> Email:
    headers = {
        h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])
    }
    return Email(
        id=msg["id"],
        thread_id=msg.get("threadId", msg["id"]),
        sender=headers.get("from", ""),
        subject=headers.get("subject", "(no subject)"),
        body=_extract_body(msg.get("payload", {})),
        received=headers.get("date", ""),
    )


def _extract_body(payload: dict) -> str:
    """Pull text/plain body, walking multipart parts."""
    if payload.get("mimeType") == "text/plain":
        return _decode(payload.get("body", {}).get("data", ""))
    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text
    # Fall back to snippet-level data if no plain part found.
    return _decode(payload.get("body", {}).get("data", ""))


def _decode(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "replace")


# ── Draft ───────────────────────────────────────────────────────────────────
def compose_reply(email: Email, reasoner: Reasoner) -> str:
    """Generate reply text (LLM). Does not touch Gmail."""
    user = f"From: {email.sender}\nSubject: {email.subject}\n\n{email.body[:6000]}"
    text = reasoner.complete(
        [
            {"role": "system", "content": _REPLY_SYSTEM},
            {"role": "user", "content": user},
        ],
        max_tokens=512,
    )
    return text.strip() if isinstance(text, str) else ""


def create_draft(
    to: str, subject: str, body: str, *, thread_id: str = "", service=None
) -> str:
    """Low-level Gmail DRAFT creation. Never sends. Returns the draft id.

    Returns 'mock-draft' when no Gmail service is configured (demo/offline).
    """
    if service is None and not _TOKEN_PATH.exists():
        return "mock-draft"

    svc = _service(service)
    mime = EmailMessage()
    mime.set_content(body)
    mime["To"] = to
    mime["Subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
    message: dict = {"raw": raw}
    if thread_id:
        message["threadId"] = thread_id
    # drafts().create — the ONLY write path. There is deliberately no send().
    draft = (
        svc.users()
        .drafts()
        .create(userId="me", body={"message": message})
        .execute()
    )
    return draft.get("id", "")


def save_draft(email: Email, body_text: str, *, service=None) -> str:
    """Save a reply to `email` as a Gmail draft (adds Re: to the subject)."""
    return create_draft(
        to=email.sender,
        subject=_reply_subject(email.subject),
        body=body_text,
        thread_id=email.thread_id,
        service=service,
    )


def _reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"
