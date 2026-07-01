"""OutlookAccount — Microsoft Graph mailbox (personal + M365).

Placeholder until the Outlook provider lands (Phase 8). Configuring an
`outlook` account today raises a clear message rather than a cryptic import
error. Read + ReadWrite scopes only — never send — will be enforced here.
"""

from __future__ import annotations


class OutlookAccount:
    kind = "outlook"

    def __init__(self, id: str, label: str = "", client_id: str = "", tenant: str = "common"):
        raise NotImplementedError(
            "Outlook support is not enabled yet. It ships in the Outlook provider "
            "phase (pip install 'inbox-to-action[outlook]')."
        )
