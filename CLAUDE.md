# CLAUDE.md — project context for Claude Code

One-pass agentic inbox triage: fetch unread mail → classify → summarize → extract
tasks → draft replies (**never sends**) → flag calendar → write `triage-report.md`.

## Commands

```bash
inbox-to-action run --since 24h [--no-drafts] [--max N] [--telegram] [--todoist] [--config PATH] [--mock]
inbox-to-action auth [--account <id>] [--config PATH] [--client-secrets PATH]
inbox-to-action mcp                      # stdio MCP server (also: python -m inbox_to_action.mcp_server)
pytest --cov=.                           # tests (LLM + Gmail mocked)
ruff check inbox_to_action/
```

## Security invariant (do not break)

Gmail scopes = `gmail.readonly` + `gmail.compose` ONLY. Outlook = `Mail.Read` +
`Mail.ReadWrite` ONLY. No send scope, no send call anywhere. Drafts only. Enforced by
`tests/test_gmail.py`. `--mock` never writes to real Gmail.

## Package layout

```
inbox_to_action/
  main.py          Typer CLI (run/auth/mcp)
  agent.py         per-email trajectory (classify→summarize→tasks→draft→calendar)
  llm_client.py    providers: claude, ollama, openrouter, nim, openai, anthropic, host
  reasoner.py      ProviderReasoner vs HostReasoner injection seam
  config.py        Settings: triage_instructions, rules[], accounts[]
  models.py        Email, Task, TriageResult, CATEGORIES
  report.py        triage-report.md renderer
  mcp_server.py    FastMCP: fetch_emails, save_gmail_draft, append_tasks, write_report
  mailboxes/       MailAccount protocol; gmail.py (works), outlook.py (stub)
  tools/           classifier, summarizer, tasks (+ Todoist), gmail (+ is_noreply),
                   calendar_flag, notify (Telegram)
  fixtures/        sample_inbox.json (--mock)
```

## Config & env

- `config.json` (gitignored; example: `config.example.json`): `triage_instructions`,
  `rules[]` (field: sender|subject|body|any → category), `accounts[]`
  (id, kind: gmail|outlook, label, client_secret?, client_id?, tenant?).
- `.env` (gitignored; example: `.env.example`): `PROVIDER`, `MODEL`, provider keys
  (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `NIM_API_KEY`/`NVIDIA_API_KEY`,
  `ANTHROPIC_API_KEY`, `OLLAMA_BASE_URL`), `TRIAGE_INSTRUCTIONS`,
  `INBOX_TO_ACTION_CONFIG`, `TODOIST_API_TOKEN`, `TELEGRAM_BOT_TOKEN`/`TELEGRAM_TOKEN`
  + `TELEGRAM_CHAT_ID`, `GMAIL_CLIENT_SECRETS`, `INBOX_TO_ACTION_TOKEN`,
  `INBOX_TO_ACTION_HTTP_TIMEOUT`.

## Categories

`action_needed` (→ tasks + draft + calendar) · `fyi` · `newsletter` · `noise`.

## Conventions

Every change via the git loop: branch → PR to `main` → squash-merge → delete branch.
Conventional commits. Small modules, type hints, tests for new behavior (mock the LLM
with `FakeReasoner`, network with `respx`).
