# 06 · MCP server & Skill (Claude Code, keyless)

Inside **Claude Code**, Claude Code itself is the LLM — no provider key needed. Two integration paths ship in the package.

---

## MCP server

Exposes four **IO-only** tools; Claude Code does the classify/summarize/extract/draft reasoning and calls these to do the I/O.

| Tool | Does |
|------|------|
| `fetch_emails(since, mock)` | returns unread emails as JSON (`mock=true` → bundled fixtures) |
| `save_gmail_draft(to, subject, body, thread_id)` | saves a reply as a Gmail **draft** (never sends) |
| `append_tasks(items, path)` | appends tasks to `tasks.md` |
| `write_report(markdown, path)` | writes `triage-report.md` |

### Register

```bash
pip install 'inbox-to-action[mcp]'
claude mcp add inbox-to-action -- python -m inbox_to_action.mcp_server
```

Verify:

```bash
claude mcp list
```

Expected output:

```text
inbox-to-action: /path/to/python -m inbox_to_action.mcp_server - ✔ Connected
```

Then, in a Claude Code session, ask it to triage your inbox — it will call `fetch_emails`, reason, then `save_gmail_draft` / `append_tasks` / `write_report`. Start with `fetch_emails(mock=true)` to try it with zero Gmail setup.

This is the same stdio server the [Glama](https://glama.ai) and [Smithery](https://smithery.ai) listings build from the bundled `Dockerfile`.

### Which Python?

`claude mcp add … -- python -m …` must point at a Python that has the package installed. If you used a venv, give its absolute path:

```bash
claude mcp add inbox-to-action -- /path/to/venv/bin/python -m inbox_to_action.mcp_server
```

---

## Skill (`/inbox-to-action`)

Copy `skills/inbox-to-action/` into your Claude Code skills directory, then type `/inbox-to-action`. The skill instructs Claude Code to fetch, reason, draft, and write the report — using the MCP tools when present, or writing the files directly as a fallback.

Both paths honor the **never-send** guarantee: drafts only.

Next: [config & triage rules →](07-config-and-triage.md)
