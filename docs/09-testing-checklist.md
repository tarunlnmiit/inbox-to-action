# 09 · Independent testing checklist

A reproducible way to verify the whole tool as a fresh user — every provider, every path — in a throwaway environment you delete afterward. Nothing here touches a shared config or sends email.

## 0 · Throwaway environment

```bash
mkdir -p /tmp/i2a-test && cd /tmp/i2a-test
python3 -m venv venv
pip install 'inbox-to-action[mcp]'
export INBOX_TO_ACTION_TOKEN=/tmp/i2a-test/token.json    # isolate Gmail token here
```

Teardown at the end: `rm -rf /tmp/i2a-test` (removes venv + token + any config).

## 1 · Install & version

- [ ] `inbox-to-action --help` works
- [ ] `python -c "import inbox_to_action; print(inbox_to_action.__version__)"`

## 2 · Mock run on **every** provider

The bundled sample inbox needs no Gmail and no account. Run each backend you have available:

```bash
PROVIDER=claude     inbox-to-action run --mock       # keyless
PROVIDER=ollama     MODEL=llama3.1 inbox-to-action run --mock
PROVIDER=openrouter OPENROUTER_API_KEY=… inbox-to-action run --mock
PROVIDER=nim        NIM_API_KEY=… inbox-to-action run --mock
PROVIDER=openai     OPENAI_API_KEY=… inbox-to-action run --mock
PROVIDER=anthropic  inbox-to-action run --mock       # key or `ant` keyless
```

- [ ] each exits 0 and writes `triage-report.md` + `tasks.md`
- [ ] categories look plausible (not everything "noise")

## 3 · Real Gmail (read-only first)

Complete [03 · Gmail OAuth](03-gmail-oauth.md) with your own app, then:

```bash
inbox-to-action auth
inbox-to-action run --since 7d --no-drafts --max 8
```

- [ ] consent screen shows **read + compose** only
- [ ] report lists real emails (widen `--since` if empty — unread only)
- [ ] `--no-drafts` wrote **no** drafts to Gmail

## 4 · Real draft + never-send proof

Force an action-needed item and let it draft (still never sends). Easiest: a `config.json` rule on a repliable sender you actually have.

```bash
inbox-to-action run --since 7d --max 8 --config config.json
```

- [ ] a draft appears in Gmail → Drafts
- [ ] **Sent** folder count is unchanged (nothing sent)
- [ ] delete the test draft afterward

## 5 · MCP in Claude Code

```bash
claude mcp add i2a-test -- /tmp/i2a-test/venv/bin/python -m inbox_to_action.mcp_server
claude mcp list                # i2a-test … Connected
```

- [ ] in a Claude Code session, `fetch_emails(mock=true)` returns fixtures
- [ ] `write_report` / `append_tasks` write files
- [ ] `claude mcp remove i2a-test` when done

## 6 · Integrations (optional)

- [ ] `--telegram` with a bot token+chat id → message arrives on your phone
- [ ] `--todoist` with a token → tasks appear in Todoist

## 7 · Teardown

```bash
claude mcp remove i2a-test 2>/dev/null || true
rm -rf /tmp/i2a-test
```

- [ ] throwaway dir gone; shared `~/.config/inbox-to-action` untouched

---

Anything fail? See [08 · Troubleshooting](08-troubleshooting.md) or open an issue.
