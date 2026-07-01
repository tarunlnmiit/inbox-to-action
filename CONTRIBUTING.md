# Contributing

Thanks for helping improve `inbox-to-action`.

## The one hard rule

**The tool must never send email.** It requests only `gmail.readonly` +
`gmail.compose` (drafts) and, for Outlook, `Mail.Read` + `Mail.ReadWrite`. No PR may
add a send scope or a send call (`messages().send`, `sendMail`, etc.). This is
enforced by tests — keep them passing.

## Dev setup

```bash
git clone https://github.com/tarunlnmiit/inbox-to-action && cd inbox-to-action
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,mcp]'
```

## Before opening a PR

```bash
ruff check inbox_to_action/          # lint
pytest --cov=. --cov-report=term-missing   # all tests pass, coverage stays high
```

- One focused change per PR.
- Add tests for new behavior (see `tests/`). Provider/network code is mocked with
  `respx`; the LLM is mocked with `FakeReasoner` (see `conftest.py`).
- Don't commit secrets — `.env` and `config.json` are gitignored. Ship
  `.env.example` / `config.example.json` changes instead.
- Match the existing style: small focused modules, type hints, no mutation of shared
  state.

## High-value contributions

- New mailbox providers (finish Outlook / Microsoft Graph — read + draft only).
- New LLM providers in `llm_client.py` (OpenAI-compatible ones are easy).
- Better classification/extraction prompts.
- New outbound notifiers (mirror `tools/notify.py`).

## Reporting bugs

Open an issue with: the exact command, the error output, your `PROVIDER`, and
Python + OS versions.
