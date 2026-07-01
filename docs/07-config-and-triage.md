# 07 · Config & triage rules

Make triage *yours*. Two layers: **deterministic rules** (run before the LLM, free and exact) and **freeform instructions** (steer the LLM). Both live in `config.json`.

## Where config is loaded from

Resolved in order (all optional — missing file → defaults, never an error):

1. `--config PATH`
2. env `INBOX_TO_ACTION_CONFIG`
3. `./config.json` in the working directory

Ship your personal file as `config.json` (gitignored). A template is committed as [`config.example.json`](../config.example.json).

## Schema

```json
{
  "triage_instructions": "Freeform guidance for the classifier.",
  "rules": [
    { "field": "sender", "contains": "hirist.tech", "category": "action_needed" },
    { "field": "subject", "contains": "invoice",    "category": "noise" },
    { "field": "any",     "contains": "unsubscribe", "category": "newsletter" }
  ],
  "accounts": [
    { "id": "personal", "kind": "gmail", "label": "Personal Gmail" }
  ]
}
```

### Rules

| Key | Values |
|-----|--------|
| `field` | `sender` · `subject` · `body` · `any` |
| `contains` | case-insensitive substring to match |
| `category` | `action_needed` · `fyi` · `newsletter` · `noise` |

The **first** matching rule wins and **skips the LLM** for that email — fast, free, deterministic. Malformed rules are dropped with a warning (bad `field`/`category`).

### Instructions

`triage_instructions` is appended to the classifier prompt. Example:

> "I'm job hunting in ML/AI — treat relevant job alerts as action_needed, not newsletter. Bank statements are fyi, not noise."

Override just the instructions per run without editing the file:

```bash
TRIAGE_INSTRUCTIONS="Treat anything from my manager as action_needed." inbox-to-action run --since 24h
```

### Accounts

See [04 · Multiple accounts](04-multi-account.md).

## The four categories

| Category | What happens |
|----------|--------------|
| `action_needed` | extract tasks + draft a reply + flag calendar |
| `fyi` | summarized, no draft |
| `newsletter` | summarized, no draft |
| `noise` | counted, minimal handling |

## Run flags that shape output

| Flag | Effect |
|------|--------|
| `--since 24h` / `3d` / `30d` | look-back window (**unread only** — widen it on quiet accounts) |
| `--max N` | cap emails per account (default 25) |
| `--no-drafts` | classify + report but create **no** Gmail drafts (safe preview) |
| `--config PATH` | use a specific config file |
| `--report-path` / `--tasks-path` | output file locations |

## No-reply suppression

Automated senders (security alerts, `notifications@`, `no-reply@`, `mailer-daemon`, …) never get a drafted reply even when classified `action_needed` — the report notes them instead. This is automatic; no config needed.

Next: [troubleshooting →](08-troubleshooting.md)
