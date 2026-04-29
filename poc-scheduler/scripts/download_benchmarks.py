"""Téléchargement des benchmarks JSSP publics depuis JSPLIB.

Source : https://github.com/tamy0612/JSPLIB

Usage :
    uv run python scripts/download_benchmarks.py taillard
    uv run python scripts/download_benchmarks.py taillard --force
    uv run python scripts/download_benchmarks.py taillard --range ta01-ta10
"""

from __future__ import annotations

import logging
import sys
import urllib.request
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

JSPLIB_RAW_BASE = "https://raw.githubusercontent.com/tamy0612/JSPLIB/master/instances"
TAILLARD_INSTANCES = [f"ta{i:02d}" for i in range(1, 81)]

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")


def _parse_range(spec: str) -> list[str]:
    """Parse une expression --range type 'ta01-ta10' ou 'ta01,ta05,ta20'."""
    spec = spec.strip()
    if "-" in spec and "," not in spec:
        start, end = spec.split("-", 1)
        try:
            start_i = int(start.removeprefix("ta"))
            end_i = int(end.removeprefix("ta"))
        except ValueError as e:
            raise click.BadParameter(f"Range invalide : {spec}") from e
        return [f"ta{i:02d}" for i in range(start_i, end_i + 1)]
    return [s.strip() for s in spec.split(",") if s.strip()]


def _download_one(name: str, dest: Path, *, force: bool, timeout: float = 30.0) -> str:
    """Télécharge une instance unique. Retourne 'downloaded', 'skipped' ou 'error: ...'."""
    if dest.exists() and not force:
        return "skipped"
    url = f"{JSPLIB_RAW_BASE}/{name}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (URL constante connue)
            content = response.read()
        dest.write_bytes(content)
        return "downloaded"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return f"error: {e}"


@click.group()
def cli() -> None:
    """Télécharge les benchmarks JSSP publics."""


@cli.command("taillard")
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_DATA_DIR,
    show_default=True,
    help="Répertoire racine des données (sous-dossier 'taillard/' créé).",
)
@click.option("--force", is_flag=True, help="Re-télécharge même si le fichier existe.")
@click.option(
    "--range",
    "range_spec",
    default=None,
    help="Sous-ensemble à télécharger (ex: 'ta01-ta10' ou 'ta01,ta05,ta20').",
)
def cmd_taillard(data_dir: Path, force: bool, range_spec: str | None) -> None:
    """Télécharge les 80 instances Taillard depuis JSPLIB."""
    target_dir = data_dir / "taillard"
    target_dir.mkdir(parents=True, exist_ok=True)

    instances = _parse_range(range_spec) if range_spec else TAILLARD_INSTANCES
    invalid = [i for i in instances if i not in TAILLARD_INSTANCES]
    if invalid:
        console.print(f"[red]Instances inconnues : {invalid}[/red]")
        sys.exit(1)

    console.print(f"[bold]Téléchargement de {len(instances)} instance(s) Taillard[/bold]")
    console.print(f"Source : {JSPLIB_RAW_BASE}")
    console.print(f"Cible  : {target_dir}\n")

    counts = {"downloaded": 0, "skipped": 0, "error": 0}
    errors: list[tuple[str, str]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Taillard", total=len(instances))
        for name in instances:
            dest = target_dir / name
            result = _download_one(name, dest, force=force)
            if result == "downloaded":
                counts["downloaded"] += 1
            elif result == "skipped":
                counts["skipped"] += 1
            else:
                counts["error"] += 1
                errors.append((name, result))
            progress.advance(task)

    console.print()
    console.print(
        f"[green]✓[/green] {counts['downloaded']} téléchargés · "
        f"[yellow]{counts['skipped']}[/yellow] déjà présents · "
        f"[red]{counts['error']}[/red] erreurs"
    )
    if errors:
        console.print("\n[red]Erreurs détaillées :[/red]")
        for name, msg in errors:
            console.print(f"  - {name} : {msg}")
        sys.exit(2)


if __name__ == "__main__":
    cli()
