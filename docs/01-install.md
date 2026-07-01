# 01 · Install

Requires **Python 3.11+**.

## Option A — pip (quickest)

```bash
pip install inbox-to-action           # core CLI
pip install 'inbox-to-action[mcp]'    # + MCP server for Claude Code
pip install 'inbox-to-action[all]'    # + MCP + Anthropic SDK
```

Isolated alternatives:

```bash
pipx install inbox-to-action          # isolated global CLI
uvx inbox-to-action run --mock        # zero-install trial (uv)
```

## Option B — Docker (MCP server)

```bash
docker run --rm ghcr.io/tarunlnmiit/inbox-to-action   # stdio MCP server
```

## Option C — from source (to customize or contribute)

```bash
git clone https://github.com/tarunlnmiit/inbox-to-action
cd inbox-to-action
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,mcp]'
```

## Verify

```bash
inbox-to-action --help
inbox-to-action run --mock            # bundled sample inbox → triage-report.md + tasks.md
```

`--mock` uses a bundled fixture inbox, so this works with **zero Gmail setup and no API key** (as long as a provider is reachable — the keyless [`claude`](02-providers.md#claude-cli-keyless) or [`ollama`](02-providers.md#ollama-local-keyless) paths are easiest).

```bash
PROVIDER=claude inbox-to-action run --mock     # keyless via local Claude Code CLI
```

You should see a `triage-report.md` and `tasks.md` in the current directory.

Next: [choose an LLM provider →](02-providers.md)
