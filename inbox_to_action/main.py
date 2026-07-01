"""inbox-to-action CLI (typer).

Commands:
  run    Triage the inbox → triage-report.md + tasks.md (+ Gmail drafts).
  auth   Run the Gmail OAuth consent flow once (read + compose scopes).
  mcp    Launch the MCP server so Claude Code can drive the tools keyless.
"""

from __future__ import annotations

import sys

import typer

try:  # Load .env so PROVIDER / API keys work as documented (optional dep).
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is a listed dependency
    pass

from inbox_to_action import agent
from inbox_to_action import llm_client
from inbox_to_action import report
from inbox_to_action.config import load_settings
from inbox_to_action.mailboxes import build_accounts
from inbox_to_action.reasoner import get_reasoner
from inbox_to_action.tools import gmail

app = typer.Typer(
    add_completion=False,
    help="Collapse inbox triage into one agentic pass: classify, summarize, "
    "extract tasks, draft replies (never sends), flag calendar.",
)


@app.command()
def run(
    since: str = typer.Option("24h", help="Look-back window, e.g. 24h or 3d."),
    mock: bool = typer.Option(
        False, "--mock", help="Use fixture emails (zero Gmail setup, free demo)."
    ),
    todoist: bool = typer.Option(
        False, "--todoist", help="Also push tasks to Todoist (needs TODOIST_API_TOKEN)."
    ),
    max_emails: int = typer.Option(
        25, "--max", help="Max emails to fetch per account (caps cost/volume)."
    ),
    no_drafts: bool = typer.Option(
        False, "--no-drafts", help="Preview only: classify + report, create NO Gmail drafts."
    ),
    report_path: str = typer.Option("triage-report.md", help="Report output path."),
    tasks_path: str = typer.Option("tasks.md", help="Tasks output path."),
    config: str = typer.Option(
        None, "--config", help="Triage config JSON (rules + instructions). "
        "Defaults to INBOX_TO_ACTION_CONFIG or ./config.json."
    ),
):
    """Fetch, triage, and write the report."""
    provider = llm_client.active_provider()
    if provider == "host":
        typer.secho(
            "PROVIDER=host has no LLM. Use the MCP server (`inbox-to-action mcp`) "
            "or the /inbox-to-action skill inside Claude Code.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    try:
        llm_client.validate_config(provider)
    except llm_client.LLMError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)

    settings = load_settings(config)
    if settings.rules or settings.triage_instructions:
        bits = []
        if settings.rules:
            bits.append(f"{len(settings.rules)} rule(s)")
        if settings.triage_instructions:
            bits.append("custom instructions")
        typer.secho(f"Triage config: {', '.join(bits)}.", fg=typer.colors.BLUE)

    accounts_map = None
    typer.secho(f"Fetching emails (since {since}, mock={mock})…", fg=typer.colors.CYAN)
    try:
        if mock:
            emails = gmail.fetch_emails(mock=True)  # single synthetic inbox
        else:
            accounts = build_accounts(settings)
            accounts_map = {a.id: a for a in accounts}
            emails = []
            for acc in accounts:
                try:
                    got = acc.fetch_emails(since=since, max_results=max_emails)
                    typer.secho(f"  {acc.label}: {len(got)} unread", fg=typer.colors.CYAN)
                    emails.extend(got)
                except Exception as e:  # noqa: BLE001 - one bad account shouldn't stop the rest
                    typer.secho(f"  {acc.label}: fetch failed ({e})", fg=typer.colors.YELLOW)
    except Exception as e:  # noqa: BLE001 - surface any fetch error cleanly
        typer.secho(f"Fetch failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not emails:
        typer.secho("No emails to triage.", fg=typer.colors.YELLOW)
        raise typer.Exit(0)

    reasoner = get_reasoner(provider)

    def progress(i: int, total: int, email):
        tag = f"[{email.account}] " if email.account else ""
        typer.echo(f"  [{i}/{total}] {tag}{email.subject[:56]}")

    mode = " (preview — no drafts)" if no_drafts else ""
    typer.secho(f"Triaging {len(emails)} emails via {provider}{mode}…", fg=typer.colors.CYAN)
    try:
        results = agent.run_agent(
            emails,
            reasoner,
            no_drafts=no_drafts,
            todoist=todoist,
            tasks_path=tasks_path,
            on_progress=progress,
            mock=mock,
            settings=settings,
            accounts=accounts_map,
        )
    except llm_client.LLMError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)

    report.write_report(results, report_path)
    counts = agent.category_counts(results)
    typer.secho(
        f"Done → {report_path}  ("
        + ", ".join(f"{k}:{v}" for k, v in counts.items())
        + ")",
        fg=typer.colors.GREEN,
    )


@app.command()
def auth(
    client_secrets: str = typer.Option(
        None, help="Path to Google OAuth client secrets JSON."
    ),
    account: str = typer.Option(
        None, "--account", help="Authorize a specific configured account by id."
    ),
    config: str = typer.Option(None, "--config", help="Triage config JSON path."),
):
    """Authorize a mailbox (Gmail read+compose, or Outlook Mail.Read+ReadWrite). Never sends."""
    settings = load_settings(config)
    accounts = build_accounts(settings)

    if account:
        target = next((a for a in accounts if a.id == account), None)
        if target is None:
            ids = ", ".join(a.id for a in accounts) or "(none configured)"
            typer.secho(f"No account '{account}'. Configured: {ids}", fg=typer.colors.RED)
            raise typer.Exit(1)
        targets = [target]
    else:
        targets = accounts

    for acc in targets:
        typer.secho(f"Authorizing {acc.label} ({acc.kind})…", fg=typer.colors.CYAN)
        try:
            if acc.kind == "gmail" and client_secrets:
                acc._client_secret = client_secrets  # honor explicit override
            acc.authorize()
        except Exception as e:  # noqa: BLE001
            typer.secho(f"Auth failed for {acc.label}: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)
    typer.secho("Authorized (read + draft scopes only). Drafts only — never sends.", fg=typer.colors.GREEN)


@app.command()
def mcp():
    """Launch the MCP server (stdio) for Claude Code integration."""
    try:
        from inbox_to_action import mcp_server
    except ImportError as e:
        typer.secho(
            f"MCP support needs the `mcp` package (pip install mcp): {e}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    mcp_server.main()


def cli():  # console-script entry point
    app()


if __name__ == "__main__":
    sys.exit(app())
