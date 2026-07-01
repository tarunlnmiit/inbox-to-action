# 08 · Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Error 403: access_denied — App has not completed the Google verification process` | The signing-in Gmail isn't a **test user** on your OAuth app | Add that exact email under OAuth consent screen → **Test users** ([03 · step 4](03-gmail-oauth.md#step-4--add-yourself-as-a-test-user-critical)) |
| Auth succeeded but **"nothing to triage" / empty report** | Only **unread** mail is fetched, and the window was too short | Widen it: `--since 7d` or `--since 30d`. Quiet accounts have little recent unread. |
| Gmail `invalid_grant` / expired after ~a week | Testing-mode refresh tokens expire ~weekly | Re-run `inbox-to-action auth`. To persist, set the OAuth app to **In production** (unverified is fine) ([03 · token expiry](03-gmail-oauth.md#token-expiry-testing-mode)) |
| OpenRouter `429 rate-limited upstream` | Free models throttle | The client retries + rotates fallbacks automatically — just retry, or set a different `MODEL` |
| `claude CLI exited 1` | Transient Claude Code CLI blip, or not signed in | Re-run. Verify with `claude --print "hi"`; sign in if needed |
| NIM request **timed out** | Big model slow on a long thread | Raise `INBOX_TO_ACTION_HTTP_TIMEOUT` (default 150) e.g. `=300` |
| `PROVIDER=host has no LLM` | `host` runs no model | Set a real `PROVIDER` ([02](02-providers.md)), or use the MCP server / Skill |
| `command not found: inbox-to-action` | Installed into a venv that isn't active | Activate that venv, or run `python -m inbox_to_action.main …`, or use the venv's absolute path |
| A no-reply address got **no draft** | Intentional — automated senders are skipped | Working as designed; the report notes "no reply — automated sender" |
| MCP server not in `claude mcp list` | Registered against the wrong Python, or config not reloaded | Point `claude mcp add` at the Python that has the package; open a new terminal ([06](06-mcp-and-skill.md)) |
| PyPI upload `403 project-scoped token is not valid for project` | A project-scoped token can't create a **new** project | First publish needs an **account-scoped** token; switch to project-scoped afterward |
| "Does it send email?!" | It cannot | Scopes are `gmail.readonly` + `gmail.compose` only; no send call exists (enforced by tests). Drafts only. |

## Getting more detail

- Add `--no-drafts` to isolate whether an issue is in triage vs draft-writing (zero Gmail writes).
- Try `--mock` to remove Gmail from the equation entirely.
- Try `PROVIDER=claude` or `PROVIDER=ollama` to remove hosted-API/rate-limit variables.

Still stuck? [Open an issue](https://github.com/tarunlnmiit/inbox-to-action/issues) with the exact command, the error output (mask secrets), your `PROVIDER`, and Python + OS.
