# 04 · Multiple accounts

Triage several inboxes in **one merged report**, each email tagged with its account. Works for multiple personal Gmail accounts and Google Workspace. (Outlook is planned.)

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
| `kind` | `gmail` (Workspace uses `gmail` too) — `outlook` is reserved for later |
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

## Backwards compatible

With **no** `accounts` block, the tool uses a single default Gmail account (the `~/.config/inbox-to-action/token.json` from a plain `inbox-to-action auth`).

Next: [integrations →](05-integrations.md)
