# Setup Guide (quickstart)

Get `inbox-to-action` triaging your inbox in a few minutes. Every step below is
optional except 1–3. **The tool never sends email — it only reads and saves drafts.**

> 📖 For the **full guides with screenshots** — per-provider setup, the detailed Google
> OAuth walkthrough, multi-account, integrations, MCP, troubleshooting, and a testing
> checklist — see **[docs/](docs/README.md)**.

---

## 1. Install

```bash
pip install inbox-to-action           # or: pipx install inbox-to-action
# from source:
git clone https://github.com/tarunlnmiit/inbox-to-action && cd inbox-to-action
pip install -e '.[mcp]'
```

Instant trial, zero setup (bundled sample inbox):

```bash
inbox-to-action run --mock
```

---

## 2. Pick an LLM backend

Set `PROVIDER` (and a key if the provider needs one) in `.env` — copy `.env.example`
first. Cheapest/keyless options first:

| `PROVIDER` | Key needed | Notes |
|------------|-----------|-------|
| `claude`   | none      | Uses your local **Claude Code** CLI. Keyless, fast. Best for testing. |
| `ollama`   | none      | Fully local. `ollama serve` + a model (e.g. `llama3.1`). Private. |
| `openrouter` | `OPENROUTER_API_KEY` | Free models available; auto-fallback + retry. **Default.** |
| `nim`      | `NIM_API_KEY` (or `NVIDIA_API_KEY`) | NVIDIA NIM. Default model `meta/llama-3.3-70b-instruct`. |
| `openai`   | `OPENAI_API_KEY` | `gpt-4o-mini` default. |
| `anthropic`| `ANTHROPIC_API_KEY` (or `ant auth login`) | `claude-opus-4-8` default. |

Override the model any time with `MODEL=...`.

```bash
# .env
PROVIDER=claude
# or: PROVIDER=openrouter  + OPENROUTER_API_KEY=...
```

---

## 3. Connect Gmail (read + draft only)

1. In [Google Cloud Console](https://console.cloud.google.com/) create an **OAuth
   client ID → Desktop app**, download the JSON as `client_secret.json` in the repo
   (or set `GMAIL_CLIENT_SECRETS=/path`). In **OAuth consent screen**, add your own
   email under **Test users** (Testing mode is fine — ignore "publish/verify").
2. Authorize (one-time browser consent):

   ```bash
   inbox-to-action auth
   ```

   Scopes requested are **`gmail.readonly` + `gmail.compose` only** — there is no send
   scope and no send call anywhere. Token caches at
   `~/.config/inbox-to-action/token.json`.

> Testing-mode refresh tokens expire ~weekly; just re-run `auth` when that happens.

---

## 4. First run (safe preview)

```bash
inbox-to-action run --since 24h --no-drafts   # report only, writes NOTHING to Gmail
```

Inspect `triage-report.md` + `tasks.md`. Happy? Drop `--no-drafts` to create drafts:

```bash
inbox-to-action run --since 24h               # creates Gmail drafts (never sends)
inbox-to-action run --since 3d --max 40        # bigger window, cap volume
```

`run` flags: `--since 24h|3d` · `--max N` (per-account cap, default 25) ·
`--no-drafts` · `--mock` · `--config PATH` · `--todoist` · `--telegram` ·
`--report-path` · `--tasks-path`.

Automated **no-reply** senders (security alerts, notifications) never get a drafted
reply — the report notes them.

---

## 5. Customize triage (optional)

Drop a `config.json` in the working dir (or point `--config` / `INBOX_TO_ACTION_CONFIG`
at one). Deterministic **rules** run before the LLM; freeform **instructions** steer it.

```json
{
  "triage_instructions": "I'm job hunting in ML/AI — treat relevant job alerts as action_needed. Bank statements are fyi.",
  "rules": [
    { "field": "sender",  "contains": "hirist.tech", "category": "action_needed" },
    { "field": "subject", "contains": "invoice",     "category": "noise" }
  ]
}
```

Fields: `sender` | `subject` | `body` | `any`. Categories: `action_needed` | `fyi` |
`newsletter` | `noise`. Env `TRIAGE_INSTRUCTIONS` overrides the file's instructions.

---

## 6. Multiple accounts (optional)

Declare accounts in `config.json` — one merged report, each email tagged by account.
Personal Gmail and Google Workspace both use the Gmail path (Workspace may need admin
approval of the OAuth app).

```json
{
  "accounts": [
    { "id": "personal", "kind": "gmail", "label": "Personal" },
    { "id": "work",     "kind": "gmail", "label": "Workspace" }
  ]
}
```

```bash
inbox-to-action auth --account personal
inbox-to-action auth --account work
inbox-to-action run --since 24h            # fetches + triages across all accounts
```

Each account caches its own token under `~/.config/inbox-to-action/tokens/<id>.json`.

---

## 7. Telegram summary (optional)

Push a concise run summary to your phone.

1. Telegram → **@BotFather** → `/newbot` → copy the token.
2. Message your bot "hi", then open
   `https://api.telegram.org/bot<token>/getUpdates` → copy `"chat":{"id": ...}`.
3. In `.env`:

   ```bash
   TELEGRAM_BOT_TOKEN=...      # TELEGRAM_TOKEN is also accepted
   TELEGRAM_CHAT_ID=...
   ```

```bash
inbox-to-action run --since 24h --telegram
```

Opt-in; a send failure never breaks the run. **Privacy:** this sends subjects + tasks
to Telegram's servers (your own chat). Notification only — never sends email.

---

## 8. Todoist (optional)

`TODOIST_API_TOKEN=...` in `.env`, then `run --todoist` to push extracted tasks.

---

## 9. Use inside Claude Code (keyless MCP)

Register the MCP server — Claude Code becomes the LLM, no provider key needed:

```bash
claude mcp add inbox-to-action -- python -m inbox_to_action.mcp_server
```

Tools exposed: `fetch_emails`, `save_gmail_draft`, `append_tasks`, `write_report`.
Or copy `skills/inbox-to-action/` into your Claude Code skills dir and run
`/inbox-to-action`.

---

## 10. Automate daily (optional)

```bash
bash setup_cron.sh        # daily 8am: run --since 24h --telegram, logged to scan.log
```

Customize with `INBOX_CRON="0 8 * * *"` / `INBOX_PYTHON=/path/to/python`.

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| `command not found: inbox-to-action` | Activate the env you installed into, or `python -m inbox_to_action.main`. |
| `PROVIDER=host has no LLM` | Set a real `PROVIDER` (see §2), or use the MCP server/skill. |
| OpenRouter `429 rate-limited` | Free models throttle; the client auto-retries + rotates fallbacks. Retry or set `MODEL`. |
| `claude CLI exited 1` | Transient Claude Code CLI blip; re-run. |
| Gmail `invalid_grant` / expired | Re-run `inbox-to-action auth` (testing-mode tokens expire ~weekly). |
| NIM read timeout | Big models are slow; raise `INBOX_TO_ACTION_HTTP_TIMEOUT` (default 150s). |
| Draft to a no-reply address | Won't happen — automated senders are skipped by design. |
