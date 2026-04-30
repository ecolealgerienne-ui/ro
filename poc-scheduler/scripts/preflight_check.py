"""CLI pour exécuter le pre-flight sur un fichier CSV ERP (verticale `mech_workshop`).

Usage :
    uv run python scripts/preflight_check.py path/to/file.csv
    uv run python scripts/preflight_check.py path/to/file.csv --today 2026-04-30
    uv run python scripts/preflight_check.py path/to/file.csv --verbose

Le moteur pre-flight est générique ; ce script l'instancie avec la config de
la verticale méca (`MECH_COLUMN_PATTERNS`, `MECH_REQUIRED_CANONICAL_FIELDS`).
Pour cibler une autre verticale, dupliquer ce script et changer l'import.

Exit codes :
    0 — pre-flight OK, peut continuer vers le LLM
    1 — bloquant détecté, retour utilisateur attendu
    2 — erreur de lecture / arguments invalides
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.preflight import PreflightReport, Severity, run_preflight
from src.verticals.mech_workshop import (
    MECH_COLUMN_PATTERNS,
    MECH_REQUIRED_CANONICAL_FIELDS,
)

console = Console()


def _severity_color(severity: Severity) -> str:
    return {
        Severity.BLOCKING: "red",
        Severity.WARNING: "yellow",
        Severity.INFO: "dim",
    }.get(severity, "white")


def _print_overview(report: PreflightReport) -> None:
    """Affiche le résumé général (séparateur, encoding, comptes)."""
    table = Table(title="Pre-flight overview", show_header=False)
    table.add_column("Champ", style="cyan")
    table.add_column("Valeur")

    table.add_row("CSV parseable", "[green]✓[/]" if report.csv_parseable else "[red]✗[/]")
    table.add_row(
        "Séparateur détecté", repr(report.detected_separator) if report.detected_separator else "—"
    )
    table.add_row("Encodage détecté", report.detected_encoding or "—")
    table.add_row("Lignes parsées", str(report.rows_parsed))
    table.add_row("Lignes cleaned", str(len(report.cleaned_rows)))
    table.add_row("Erreurs bloquantes", f"[red]{report.blocking_count}[/]")
    table.add_row("Warnings", f"[yellow]{report.warning_count}[/]")

    console.print(table)


def _print_mapping(report: PreflightReport) -> None:
    if not report.column_mapping_suggested:
        console.print("\n[yellow]⚠ Aucun mapping de colonnes détecté[/]")
        return
    table = Table(title="Mapping colonnes (heuristique)")
    table.add_column("Source", style="cyan")
    table.add_column("→")
    table.add_column("Canonique", style="bright_green")
    for source, canonical in sorted(report.column_mapping_suggested.items()):
        table.add_row(source, "→", canonical)
    console.print()
    console.print(table)


def _print_errors(report: PreflightReport, verbose: bool) -> None:
    if not report.errors:
        return
    table = Table(title=f"Erreurs ({len(report.errors)})")
    table.add_column("Sévérité")
    table.add_column("Type", style="cyan")
    table.add_column("Ligne", justify="right")
    table.add_column("Colonne")
    table.add_column("Valeur brute")
    table.add_column("Description" if verbose else "Description (tronquée)")

    # Limite d'affichage en mode non-verbose
    items = report.errors if verbose else report.errors[:10]
    for err in items:
        sev_color = _severity_color(err.severity)
        desc = (
            err.description
            if verbose
            else (err.description[:80] + "…" if len(err.description) > 80 else err.description)
        )
        table.add_row(
            f"[{sev_color}]{err.severity.value}[/]",
            err.type.value,
            str(err.row_index) if err.row_index is not None else "—",
            err.column or "—",
            err.raw_value or "—",
            desc,
        )
    if not verbose and len(report.errors) > 10:
        table.caption = (
            f"… {len(report.errors) - 10} autres erreurs (utilise --verbose pour tout voir)"
        )
    console.print()
    console.print(table)


def _print_verdict(report: PreflightReport) -> int:
    should, reason = report.should_call_llm()
    console.print()
    if should:
        console.print(
            Panel(
                f"[green]✓ Pre-flight OK[/]\nReason : {reason}\nLe fichier peut être passé au LLM.",
                title="Verdict",
                border_style="green",
            )
        )
        return 0
    console.print(
        Panel(
            f"[red]✗ Pre-flight BLOQUANT[/]\nReason : {reason}\nRetour utilisateur attendu, pas d'appel LLM.",
            title="Verdict",
            border_style="red",
        )
    )
    return 1


@click.command()
@click.argument(
    "csv_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--today",
    "today_iso",
    type=str,
    default=None,
    help="Date de référence pour `date_passee` (format YYYY-MM-DD). Défaut : aujourd'hui.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Affiche toutes les erreurs en détail.",
)
def cli(csv_path: Path, today_iso: str | None, verbose: bool) -> None:
    """Exécute le pre-flight sur un CSV et affiche le rapport."""
    if today_iso is not None:
        try:
            today = date.fromisoformat(today_iso)
        except ValueError:
            console.print(f"[red]✗ --today doit être au format YYYY-MM-DD, reçu : {today_iso}[/]")
            sys.exit(2)
    else:
        today = date.today()

    console.print(f"[bold]Pre-flight[/] sur [cyan]{csv_path}[/] (today={today.isoformat()})")
    report = run_preflight(
        csv_path,
        column_patterns=MECH_COLUMN_PATTERNS,
        required_canonical_fields=MECH_REQUIRED_CANONICAL_FIELDS,
        today=today,
    )

    _print_overview(report)
    _print_mapping(report)
    _print_errors(report, verbose=verbose)
    exit_code = _print_verdict(report)
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
