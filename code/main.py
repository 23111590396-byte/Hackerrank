"""
SupportBrain — main.py
CLI entry point. Loads corpus, processes all tickets, writes output.csv.
Rich terminal UI with progress display.

Usage:
    python code/main.py [--input PATH] [--output PATH] [--verbose]
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

# ── locate repo root (main.py lives in code/) ──────────────────────────────
REPO_ROOT = str(Path(__file__).resolve().parent.parent)
# Ensure code/ is on the Python path for sibling imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

import agent
import logger
from retriever import Retriever

# Load .env (looks in code/ first, then repo root)
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(Path(REPO_ROOT) / ".env")

console = Console()

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_INPUT = str(Path(REPO_ROOT) / "support_issues" / "support_issues.csv")
DEFAULT_OUTPUT = str(Path(REPO_ROOT) / "support_issues" / "output.csv")

OUTPUT_COLUMNS = [
    "Issue", "Subject", "Company",
    "response", "product_area", "status", "request_type", "justification",
]

STATUS_COLOR = {"Replied": "green", "Escalated": "red"}
PROVIDER_ICON = {"groq": "⚡ groq", "gemini": "🌀 gemini", "none": "–"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_tickets(path: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _write_output(path: str, results: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
def _print_banner() -> None:
    banner = (
        "[bold cyan]🧠  SupportBrain — Multi-Domain Triage Agent[/bold cyan]\n"
        "[dim]HackerRank Orchestrate · May 2026[/dim]\n"
        "[dim]Powered by: Groq (primary) + Gemini (fallback)  ·  Cost: $0.00[/dim]"
    )
    console.print(Panel(banner, border_style="cyan", padding=(1, 4)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="SupportBrain — Triage Agent")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to support_issues.csv")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to output.csv")
    parser.add_argument("--verbose", action="store_true", help="Print per-ticket details")
    args = parser.parse_args()

    _print_banner()

    # Check API keys
    groq_key = os.getenv("GROQ_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not groq_key and not gemini_key:
        console.print(
            "[bold red]ERROR:[/bold red] No API keys found. "
            "Copy code/.env.example to code/.env and add your keys."
        )
        sys.exit(1)
    if not groq_key:
        console.print("[yellow]⚠  GROQ_API_KEY not set — will use Gemini only.[/yellow]")
    if not gemini_key:
        console.print("[yellow]⚠  GEMINI_API_KEY not set — will use Groq only.[/yellow]")

    # Load corpus
    console.print("\n[bold]Loading corpus...[/bold]")
    retriever = Retriever(REPO_ROOT)
    with console.status("[cyan]Building TF-IDF index...[/cyan]"):
        counts = retriever.load_all()
    for company, n in counts.items():
        console.print(f"  [green]✓[/green] {company}: {n} chunks indexed")

    # Init DB + log dir
    logger.init_db(REPO_ROOT)
    logger._ensure_log_dir()

    # Read tickets
    tickets = _read_tickets(args.input)
    total = len(tickets)
    console.print(f"\n[bold]Processing {total} tickets...[/bold]\n")

    results: list[dict] = []
    start_time = time.time()

    # Live results table
    live_table = Table(
        "  #  ", "Company", "Status", "Type", "Area", "Provider",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold magenta",
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("[cyan]Triaging tickets", total=total)

        for idx, ticket in enumerate(tickets, start=1):
            subject = ticket.get("Subject", "")[:40]
            company_raw = ticket.get("Company", "?")
            progress.update(
                task,
                description=f"[cyan]#{idx:02d}/{total}[/cyan] {company_raw[:12]:12s} — {subject}",
            )

            result = agent.run(ticket, idx, retriever, REPO_ROOT)
            results.append(result)

            status = result["status"]
            color = STATUS_COLOR.get(status, "white")
            provider_label = PROVIDER_ICON.get(result.get("provider_used", "none"), "–")

            live_table.add_row(
                str(idx),
                result.get("Company", "Unknown"),
                f"[{color}]{status}[/{color}]",
                result.get("request_type", ""),
                result.get("product_area", ""),
                provider_label,
            )

            if args.verbose:
                console.print(
                    f"  [dim]#{idx:02d}[/dim] [{color}]{status}[/{color}]  "
                    f"{result.get('product_area','')}  "
                    f"({result.get('provider_used','none')})"
                )

            progress.advance(task)

    elapsed = time.time() - start_time

    console.print()
    console.print(live_table)

    # Write output
    _write_output(args.output, results)

    # Final summary
    replied = sum(1 for r in results if r["status"] == "Replied")
    escalated = sum(1 for r in results if r["status"] == "Escalated")
    groq_n = sum(1 for r in results if r.get("provider_used") == "groq")
    gemini_n = sum(1 for r in results if r.get("provider_used") == "gemini")
    skipped = sum(1 for r in results if r.get("provider_used") == "none")

    summary = (
        f"[bold green]✅  Done![/bold green] Processed [bold]{total}[/bold] tickets "
        f"in [bold]{elapsed:.1f}s[/bold]\n"
        f"📄  Output  → [cyan]{args.output}[/cyan]\n"
        f"📋  Log     → [cyan]{logger.LOG_FILE}[/cyan]\n"
        f"🗄   Audit   → [cyan]{REPO_ROOT}/code/audit.db[/cyan]\n\n"
        f"[green]Replied  :[/green] {replied}   "
        f"[red]Escalated:[/red] {escalated}\n\n"
        f"Provider breakdown:\n"
        f"  ⚡ Groq   : {groq_n} calls\n"
        f"  🌀 Gemini : {gemini_n} calls\n"
        f"  –  Skipped: {skipped} (escalated before LLM)\n"
        f"\n[bold]💰 Total cost: $0.00[/bold]"
    )
    console.print(Panel(summary, border_style="green", title="Summary", padding=(1, 4)))


if __name__ == "__main__":
    main()
