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

    typer.secho(f"Fetching emails (since {since}, mock={mock})…", fg=typer.colors.CYAN)
    try:
        emails = gmail.fetch_emails(since=since, mock=mock)
    except Exception as e:  # noqa: BLE001 - surface any fetch error cleanly
        typer.secho(f"Fetch failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not emails:
        typer.secho("No emails to triage.", fg=typer.colors.YELLOW)
        raise typer.Exit(0)

    reasoner = get_reasoner(provider)
    settings = load_settings(config)
    if settings.rules or settings.triage_instructions:
        bits = []
        if settings.rules:
            bits.append(f"{len(settings.rules)} rule(s)")
        if settings.triage_instructions:
            bits.append("custom instructions")
        typer.secho(f"Triage config: {', '.join(bits)}.", fg=typer.colors.BLUE)

    def progress(i: int, total: int, email):
        typer.echo(f"  [{i}/{total}] {email.subject[:60]}")

    typer.secho(f"Triaging {len(emails)} emails via {provider}…", fg=typer.colors.CYAN)
    try:
        results = agent.run_agent(
            emails,
            reasoner,
            todoist=todoist,
            tasks_path=tasks_path,
            on_progress=progress,
            mock=mock,
            settings=settings,
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
    )
):
    """Run the Gmail OAuth consent flow (read + compose scopes only)."""
    try:
        gmail.get_credentials(client_secrets)
    except Exception as e:  # noqa: BLE001
        typer.secho(f"Auth failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho("Gmail authorized (read + compose). Drafts only — never sends.", fg=typer.colors.GREEN)


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
