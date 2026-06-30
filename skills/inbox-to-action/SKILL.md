---
name: inbox-to-action
description: Triage an inbox in one agentic pass — fetch unread email, classify, summarize long threads, extract tasks, draft replies (never sends), flag calendar blocks. Keyless: you are the LLM. Trigger when the user says /inbox-to-action or asks to triage their inbox.
---

# inbox-to-action (host mode)

You are the reasoning engine. No LLM API key is needed — you classify, summarize,
extract, and draft directly, then call the project's IO tools to persist results.

## Steps

1. **Fetch.** Run the fetch step. For a zero-setup demo use mock fixtures:
   ```
   inbox-to-action run --mock --help   # confirm CLI is installed
   ```
   To get the raw emails as JSON, prefer the MCP tool `fetch_emails` if the
   inbox-to-action MCP server is connected. Otherwise read
   `fixtures/sample_inbox.json` (mock) or ask the user to run `inbox-to-action auth`
   first for real Gmail.

2. **Classify** each email into exactly one of: `action_needed`, `fyi`,
   `newsletter`, `noise`.

3. **Summarize** any thread longer than ~500 words into two lines.

4. For each `action_needed` email:
   - **Extract tasks** (with deadlines if stated).
   - **Draft a reply** — concise, professional, body only. Save it via the MCP
     tool `save_gmail_draft(to, subject, body, thread_id)`. NEVER send.
   - **Flag for calendar** if it implies a meeting or time block.

5. **Persist:**
   - Tasks → `append_tasks([{text, deadline}])` (writes `tasks.md`).
   - Report → `write_report(markdown)` (writes `triage-report.md`) with sections
     per category, drafted-reply previews, a tasks summary, and a calendar list.

## Rules

- **Drafts only, never send.** The tools have no send capability; do not attempt it.
- Keep the whole pass under ~60 seconds for a demo.
- If the MCP server is not connected, do the reasoning anyway and write
  `triage-report.md` / `tasks.md` directly with the Write tool; tell the user to
  connect the MCP server (`claude mcp add inbox-to-action -- inbox-to-action mcp`)
  to enable real Gmail drafts.
