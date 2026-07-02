# 04 · Multiple accounts

Triage several inboxes in **one merged report**, each email tagged with its account. Works for multiple personal Gmail accounts, Google Workspace, and Outlook (personal outlook.com + Microsoft 365).

## Declare accounts in `config.json`

```json
{
  "accounts": [
    { "id": "personal", "kind": "gmail", "label": "Personal Gmail" },
    { "id": "work",     "kind": "gmail", "label": "Workspace", "client_secret": "work_client_secret.json" }
  ]
}
```

Fields per account:

| Field | Meaning |
|-------|---------|
| `id` | short unique id (used for the token filename and report tag) |
| `kind` | `gmail` (Workspace uses `gmail` too) or `outlook` |
| `label` | display name in the report |
| `client_secret` | optional path to that account's OAuth secret (defaults to the shared one) |

> Multiple personal Gmail accounts can reuse **one** `client_secret.json` — each gets its own cached token. Just add each account's email as a test user on that OAuth app (see [03 · Gmail OAuth](03-gmail-oauth.md#step-4--add-yourself-as-a-test-user-critical)).

## Authorize each account once

```bash
inbox-to-action auth --account personal
inbox-to-action auth --account work
```

Each caches its own token at `~/.config/inbox-to-action/tokens/<id>.json`. Deleting one file de-authorizes just that account.

## Run across all accounts

```bash
inbox-to-action run --since 24h
```

The report tags each item with its account, e.g. *`from … · personal`*. Drafts are saved back to the **originating** account. If one account fails to fetch, it's warned and skipped — the rest still run.

## Google Workspace note

A Workspace (company) account uses the same `gmail` path. Your Workspace **admin** may need to allow the OAuth app (app access control) before you can authorize it. Personal Gmail has no such gate.

## Add an Outlook account

Outlook (personal outlook.com/live **and** Microsoft 365) uses your own free Azure app. Scopes requested are **`Mail.Read` + `Mail.ReadWrite` only — never send.**

1. Install the extra: `pip install 'inbox-to-action[outlook]'`.
2. Go to <https://portal.azure.com> → **Microsoft Entra ID → App registrations → New registration**.
   - Supported account types: **Accounts in any org directory and personal Microsoft accounts**.
   - Redirect URI: **Public client/native** → `http://localhost`.
   - Register → copy the **Application (client) ID**.
3. **API permissions → Add → Microsoft Graph → Delegated** → add **`Mail.Read`** and **`Mail.ReadWrite`** (do *not* add `Mail.Send`).
4. Add the account to `config.json`:

   ```json
   { "id": "outlook", "kind": "outlook", "label": "Outlook",
     "client_id": "YOUR_APPLICATION_CLIENT_ID", "tenant": "common" }
   ```

5. Authorize (browser consent, once): `inbox-to-action auth --account outlook`.

Drafts are created via Graph `createReply` — saved to your Outlook **Drafts**, never sent. `tenant` stays `common` for personal + multi-org; use your tenant id to lock to one org.

## Backwards compatible

With **no** `accounts` block, the tool uses a single default Gmail account (the `~/.config/inbox-to-action/token.json` from a plain `inbox-to-action auth`).

Next: [integrations →](05-integrations.md)
