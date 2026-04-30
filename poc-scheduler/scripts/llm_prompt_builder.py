"""Construit un prompt prêt-à-coller pour Claude.ai en combinant pre-flight + template.

Pipeline :
    CSV brut → run_preflight() → si OK : template prompt_v3 + variables → stdout/fichier

Usage :
    # Prompt complet vers stdout (à pipe ou copier)
    uv run python scripts/llm_prompt_builder.py path/to/file.csv

    # Écrit dans un fichier
    uv run python scripts/llm_prompt_builder.py path/to/file.csv --output prompt.txt

    # Avec une date de référence custom (pour reproduire un test)
    uv run python scripts/llm_prompt_builder.py path/to/file.csv --today 2026-04-30

    # Choisir un autre template
    uv run python scripts/llm_prompt_builder.py path/to/file.csv --prompt prompt_v2.md

Exit codes :
    0 — Prompt généré
    1 — Pre-flight bloquant (le fichier n'a pas atteint le LLM)
    2 — Erreur d'arguments / fichier introuvable

Ergonomie :
    cat prompt.txt | xclip -sel clip   # ou pbcopy sur macOS
    # puis Cmd+V dans Claude.ai
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import click
from rich.console import Console

from src.preflight import PreflightReport, Severity, run_preflight

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS_DIR = REPO_ROOT.parent / "experiments" / "llm-extraction"

stderr = Console(stderr=True)


def _build_mapping_table(report: PreflightReport) -> str:
    """Markdown table du mapping colonnes."""
    if not report.column_mapping_suggested:
        return "_(aucun mapping détecté)_"
    lines = ["| Source | Canonique |", "|--------|-----------|"]
    for source, canonical in sorted(report.column_mapping_suggested.items()):
        lines.append(f"| `{source}` | `{canonical}` |")
    return "\n".join(lines)


def _build_preflight_anomalies_json(report: PreflightReport) -> str:
    """JSON list des anomalies WARNING déjà détectées (à passer au LLM)."""
    items = []
    for err in report.errors:
        # Seuls les warnings sont passés au LLM (les bloquants ont arrêté la procédure).
        if err.severity != Severity.WARNING:
            continue
        items.append(
            {
                "type": err.type.value,
                "row_reference": (
                    f"ligne {err.row_index}" if err.row_index is not None else "global"
                ),
                "raw_value": err.raw_value or "",
                "description": err.description,
            }
        )
    return json.dumps(items, ensure_ascii=False, indent=2)


def _build_cleaned_csv(report: PreflightReport) -> str:
    """Reconstruit un CSV depuis les cleaned_rows (avec dates ISO)."""
    if not report.cleaned_rows:
        return ""
    headers = list(report.cleaned_rows[0].cells.keys())
    sep = report.detected_separator or ";"
    lines = [sep.join(headers)]
    for row in report.cleaned_rows:
        values = [row.cells.get(h, "") for h in headers]
        lines.append(sep.join(values))
    return "\n".join(lines)


def _print_blocking_details(report: PreflightReport) -> None:
    """Affiche un diagnostic compact sur stderr quand le pre-flight bloque."""
    stderr.print()
    stderr.print(f"[red]✗ Pre-flight bloquant — pas d'appel LLM[/]")
    should, reason = report.should_call_llm()
    stderr.print(f"  Raison : {reason}")
    blocking = [e for e in report.errors if e.severity == Severity.BLOCKING]
    if blocking:
        stderr.print(f"  {len(blocking)} erreur(s) bloquante(s) :")
        for err in blocking[:5]:
            location = (
                f"ligne {err.row_index}, colonne {err.column!r}"
                if err.row_index is not None
                else "global"
            )
            stderr.print(f"    - [{err.type.value}] {location} : {err.description}")
        if len(blocking) > 5:
            stderr.print(f"    … {len(blocking) - 5} autres")
    stderr.print()
    stderr.print(
        "  Lancer `uv run python scripts/preflight_check.py <file>` pour le détail complet."
    )


@click.command()
@click.argument(
    "csv_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--prompt",
    "prompt_name",
    default="prompt_v3.md",
    show_default=True,
    help="Nom du template à utiliser (dans experiments/llm-extraction/).",
)
@click.option(
    "--schema",
    "schema_name",
    default="target_schema.md",
    show_default=True,
    help="Nom du schéma cible.",
)
@click.option(
    "--today",
    "today_iso",
    default=None,
    help="Date de référence pour `date_passee` (format YYYY-MM-DD). Défaut : aujourd'hui.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Si fourni, écrit dans ce fichier. Sinon, stdout.",
)
def cli(
    csv_path: Path,
    prompt_name: str,
    schema_name: str,
    today_iso: str | None,
    output_path: Path | None,
) -> None:
    """Génère un prompt prêt-à-coller pour Claude.ai à partir d'un CSV ERP."""
    if today_iso is not None:
        try:
            today = date.fromisoformat(today_iso)
        except ValueError:
            stderr.print(f"[red]✗ --today doit être YYYY-MM-DD, reçu : {today_iso}[/]")
            sys.exit(2)
    else:
        today = date.today()

    prompt_template_path = EXPERIMENTS_DIR / prompt_name
    schema_path = EXPERIMENTS_DIR / schema_name
    if not prompt_template_path.exists():
        stderr.print(f"[red]✗ Template introuvable : {prompt_template_path}[/]")
        sys.exit(2)
    if not schema_path.exists():
        stderr.print(f"[red]✗ Schéma introuvable : {schema_path}[/]")
        sys.exit(2)

    # 1. Pre-flight
    report = run_preflight(csv_path, today=today)
    should_call, _reason = report.should_call_llm()
    if not should_call:
        _print_blocking_details(report)
        sys.exit(1)

    # 2. Substitution dans le template
    prompt = prompt_template_path.read_text(encoding="utf-8")
    schema = schema_path.read_text(encoding="utf-8")
    prompt = prompt.replace("{{SCHEMA}}", schema)
    prompt = prompt.replace("{{SEPARATOR}}", report.detected_separator or "?")
    prompt = prompt.replace("{{ENCODING}}", report.detected_encoding or "?")
    prompt = prompt.replace("{{TODAY}}", today.isoformat())
    prompt = prompt.replace("{{COLUMN_MAPPING}}", _build_mapping_table(report))
    prompt = prompt.replace("{{PREFLIGHT_ANOMALIES}}", _build_preflight_anomalies_json(report))
    prompt = prompt.replace("{{CSV}}", _build_cleaned_csv(report))

    # 3. Sortie
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")
        stderr.print(
            f"[green]✓[/] Prompt écrit dans {output_path} "
            f"({len(prompt):,} caractères, ~{len(prompt) // 4:,} tokens approx.)"
        )
        stderr.print(
            f"  Pre-flight : {report.warning_count} warning(s) injecté(s), "
            f"{len(report.cleaned_rows)} ligne(s) à analyser"
        )
    else:
        # stdout : print le prompt brut, infos pre-flight sur stderr
        stderr.print(
            f"[dim]Pre-flight OK — "
            f"{report.warning_count} warning(s), "
            f"{len(report.cleaned_rows)} ligne(s) cleaned, "
            f"~{len(prompt) // 4:,} tokens[/]"
        )
        click.echo(prompt)


if __name__ == "__main__":
    cli()
