"""Local CLI entry — useful for testing without spinning up the server."""

from __future__ import annotations

import json
import logging
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from .pipeline import run_pipeline

app = typer.Typer(help="ContentFarm — multi-agent short-form script generator")
console = Console()


@app.command()
def generate(
    topic: str = typer.Argument(..., help="The topic to generate a script for."),
    json_out: bool = typer.Option(False, "--json", help="Print full pipeline result as JSON."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
):
    """Run the full pipeline for TOPIC and print the resulting script."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = run_pipeline(topic)

    if json_out:
        json.dump(result.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    console.print(Rule(f"[bold cyan]ContentFarm — {topic}[/bold cyan]"))

    if result.final_hook:
        console.print(
            Panel(
                f"[bold]{result.final_hook.hook_text}[/bold]\n\n"
                f"scroll_stop={result.final_hook.scroll_stop} "
                f"curiosity={result.final_hook.curiosity_gap} "
                f"specificity={result.final_hook.specificity} "
                f"stakes={result.final_hook.stakes} "
                f"compression={result.final_hook.compression}",
                title="Locked Hook",
                border_style="green" if result.final_hook.passes_gate else "yellow",
            )
        )

    console.print(Rule("[bold]Final Script[/bold]"))
    for line in result.final_script_lines:
        console.print(f"  {line}")

    rewrites = sum(len(a["attempts"]) - 1 for a in result.line_audit)
    console.print(Rule(
        f"[dim]Lines: {len(result.final_script_lines)} • "
        f"Rewrites: {rewrites} • "
        f"Research: yt={len(result.research.youtube)} "
        f"reddit={len(result.research.reddit)} x={len(result.research.x)}[/dim]"
    ))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
