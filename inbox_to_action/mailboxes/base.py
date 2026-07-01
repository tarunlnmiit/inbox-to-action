"""MailAccount protocol + account factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from inbox_to_action.models import Email

_KINDS = ("gmail", "outlook")


@dataclass(frozen=True)
class AccountConfig:
    id: str
    kind: str  # one of _KINDS
    label: str = ""
    client_secret: str = ""  # gmail: path to OAuth client secrets JSON
    client_id: str = ""  # outlook: Azure app (client) id
    tenant: str = "common"  # outlook: authority tenant


@runtime_checkable
class MailAccount(Protocol):
    id: str
    kind: str
    label: str

    def fetch_emails(self, *, since: str = "24h", max_results: int = 50) -> list[Email]:
        ...

    def create_draft(
        self, to: str, subject: str, body: str, *, thread_id: str = "", mock: bool = False
    ) -> str:
        ...

    def save_draft(self, email: Email, body: str, *, mock: bool = False) -> str:
        ...

    def authorize(self) -> None:
        ...


def _coerce_accounts(raw) -> tuple[AccountConfig, ...]:
    """Build AccountConfig objects from raw dicts, dropping malformed ones."""
    out: list[AccountConfig] = []
    if not isinstance(raw, list):
        return ()
    for item in raw:
        if not isinstance(item, dict):
            continue
        acc_id = str(item.get("id", "")).strip()
        kind = str(item.get("kind", "")).strip().lower()
        if not acc_id or kind not in _KINDS:
            continue
        out.append(
            AccountConfig(
                id=acc_id,
                kind=kind,
                label=str(item.get("label", acc_id)),
                client_secret=str(item.get("client_secret", "")),
                client_id=str(item.get("client_id", "")),
                tenant=str(item.get("tenant", "common")) or "common",
            )
        )
    return tuple(out)


def build_accounts(settings) -> list[MailAccount]:
    """Instantiate mail accounts from settings.

    Back-compat: when no accounts are configured, return a single default Gmail
    account that uses the legacy `client_secret.json` + token path.
    """
    from inbox_to_action.mailboxes.gmail import GmailAccount

    configs = getattr(settings, "accounts", ()) or ()
    if not configs:
        return [GmailAccount(id="default", label="gmail")]

    accounts: list[MailAccount] = []
    for cfg in configs:
        if cfg.kind == "gmail":
            accounts.append(
                GmailAccount(
                    id=cfg.id,
                    label=cfg.label or cfg.id,
                    client_secret=cfg.client_secret or None,
                )
            )
        elif cfg.kind == "outlook":
            # Outlook provider lands in a later phase; import lazily so its
            # optional dependency (msal) isn't required for Gmail-only setups.
            from inbox_to_action.mailboxes.outlook import OutlookAccount

            accounts.append(
                OutlookAccount(
                    id=cfg.id,
                    label=cfg.label or cfg.id,
                    client_id=cfg.client_id,
                    tenant=cfg.tenant,
                )
            )
    return accounts
