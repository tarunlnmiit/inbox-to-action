# inbox-to-action — Documentation

One command triages your inbox: **classify → summarize → extract tasks → draft replies → flag calendar**, in a single agentic pass. It saves replies as **Gmail drafts** and **never sends email**.

> 🔒 **Drafts only — never sends.** Gmail scopes are `gmail.readonly` + `gmail.compose` only. There is no send scope and no send call anywhere (enforced by tests). You review every draft and hit send yourself.

## Guides

| # | Guide | What it covers |
|---|-------|----------------|
| 01 | [Install](01-install.md) | pip / pipx / uvx / Docker / from source |
| 02 | [LLM providers](02-providers.md) | Every backend: claude CLI, Ollama, OpenRouter, NIM, OpenAI, Anthropic, host |
| 03 | [Gmail OAuth setup](03-gmail-oauth.md) | Create your own Google OAuth app → `client_secret.json` → `auth` |
| 04 | [Multiple accounts](04-multi-account.md) | Several Gmail / Google Workspace inboxes in one run |
| 05 | [Integrations](05-integrations.md) | Telegram summaries + Todoist tasks |
| 06 | [MCP server & Skill](06-mcp-and-skill.md) | Use it keyless inside Claude Code |
| 07 | [Config & triage rules](07-config-and-triage.md) | Make triage yours: rules + instructions |
| 08 | [Troubleshooting](08-troubleshooting.md) | Every error we've hit, and the fix |
| 09 | [Testing checklist](09-testing-checklist.md) | Reproducible independent test — every provider, every path |

## Provider matrix

| `PROVIDER` | Key needed | Default model | Best for |
|------------|-----------|---------------|----------|
| `claude`   | none (local Claude Code CLI) | your CLI default | fastest keyless test |
| `ollama`   | none (local) | `llama3.1` | fully private / offline |
| `openrouter` (default) | `OPENROUTER_API_KEY` | `google/gemma-4-31b-it:free` | free hosted models |
| `nim`      | `NIM_API_KEY` / `NVIDIA_API_KEY` | `meta/llama-3.3-70b-instruct` | strong free models |
| `openai`   | `OPENAI_API_KEY` | `gpt-4o-mini` | cheap paid |
| `anthropic`| `ANTHROPIC_API_KEY` or `ant auth login` | `claude-opus-4-8` | best quality |
| `host`     | none | — | MCP / Skill (Claude Code is the LLM) |

## 60-second trial (zero setup)

```bash
pip install inbox-to-action
inbox-to-action run --mock          # bundled sample inbox, no Gmail, no key needed
```

Then follow [01-install](01-install.md) → [02-providers](02-providers.md) → [03-gmail-oauth](03-gmail-oauth.md) for the real thing.

---

Screenshots in these guides have all sensitive values (emails, API keys, client IDs/secrets, tokens) blurred. Contributors: see [CAPTURE-CHECKLIST.md](CAPTURE-CHECKLIST.md).
