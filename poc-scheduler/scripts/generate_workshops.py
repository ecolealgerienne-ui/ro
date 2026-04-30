"""CLI pour générer des ateliers de mécanique de précision synthétiques.

Usage :
    uv run python scripts/generate_workshops.py single --output workshop.json
    uv run python scripts/generate_workshops.py single --machines 15 --jobs 200 --seed 42
    uv run python scripts/generate_workshops.py batch --count 50 --output data/synthetic/batch01/
"""

from __future__ import annotations

import sys
import time
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
from rich.table import Table

from src.verticals.mech_workshop.generator import (
    GenerationParams,
    SyntheticWorkshop,
    generate_workshop,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "synthetic"

console = Console()


def _build_params(
    seed: int,
    machines: int | None,
    jobs: int | None,
    operators: int | None,
    horizon_days: int,
    ops_per_job: tuple[int, int],
) -> GenerationParams:
    """Construit `GenerationParams` à partir des options CLI."""
    extras: dict[str, int] = {}
    if machines is not None:
        extras["n_machines_min"] = machines
        extras["n_machines_max"] = machines
    if jobs is not None:
        extras["n_jobs_min"] = jobs
        extras["n_jobs_max"] = jobs
    if operators is not None:
        extras["n_operators_min"] = operators
        extras["n_operators_max"] = operators
    return GenerationParams(
        seed=seed,
        planning_horizon_days=horizon_days,
        operations_per_job_min=ops_per_job[0],
        operations_per_job_max=ops_per_job[1],
        **extras,
    )


def _summary_table(workshop: SyntheticWorkshop) -> Table:
    table = Table(title="Résumé atelier généré", show_header=False)
    table.add_column("Champ", style="cyan")
    table.add_column("Valeur")
    table.add_row("Machines", str(len(workshop.machines)))
    table.add_row("Opérateurs", str(len(workshop.operators)))
    table.add_row("OF", str(len(workshop.orders)))
    n_ops_total = sum(len(o.operations) for o in workshop.orders)
    table.add_row("Opérations totales", str(n_ops_total))
    if workshop.orders:
        avg_ops = n_ops_total / len(workshop.orders)
        table.add_row("Opérations / OF (moy.)", f"{avg_ops:.1f}")
    table.add_row("Seed", str(workshop.metadata.get("seed", "—")))
    return table


def _save_json(workshop: SyntheticWorkshop, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workshop.model_dump_json(indent=2), encoding="utf-8")


@click.group()
def cli() -> None:
    """Génération d'ateliers méca synthétiques pour stress-test du solveur."""


@cli.command("single")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=DEFAULT_OUTPUT_DIR / "workshop.json",
    show_default=True,
    help="Chemin du fichier JSON de sortie.",
)
@click.option("--seed", default=42, type=int, show_default=True)
@click.option(
    "--machines", default=None, type=int, help="Nombre de machines fixé (sinon range défaut)."
)
@click.option("--operators", default=None, type=int, help="Nombre d'opérateurs fixé.")
@click.option("--jobs", default=None, type=int, help="Nombre d'OF fixé.")
@click.option("--horizon-days", default=10, type=int, show_default=True)
@click.option(
    "--ops-per-job",
    nargs=2,
    type=int,
    default=(2, 8),
    show_default=True,
    help="Min et max d'opérations par OF.",
)
def cmd_single(
    output: Path,
    seed: int,
    machines: int | None,
    operators: int | None,
    jobs: int | None,
    horizon_days: int,
    ops_per_job: tuple[int, int],
) -> None:
    """Génère un seul atelier et l'exporte en JSON."""
    params = _build_params(seed, machines, jobs, operators, horizon_days, ops_per_job)

    t0 = time.perf_counter()
    workshop = generate_workshop(params)
    elapsed = time.perf_counter() - t0

    _save_json(workshop, output)

    console.print(_summary_table(workshop))
    console.print(f"\n[green]✓[/green] Atelier généré en {elapsed * 1000:.0f} ms")
    console.print(f"   Écrit dans : {output}")


@cli.command("batch")
@click.option("--count", required=True, type=int, help="Nombre d'ateliers à générer.")
@click.option(
    "--output",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_OUTPUT_DIR / "batch",
    show_default=True,
    help="Dossier de sortie.",
)
@click.option(
    "--seed-base", default=42, type=int, show_default=True, help="Seed du premier atelier."
)
@click.option("--machines", default=None, type=int)
@click.option("--operators", default=None, type=int)
@click.option("--jobs", default=None, type=int)
@click.option("--horizon-days", default=10, type=int, show_default=True)
@click.option("--ops-per-job", nargs=2, type=int, default=(2, 8), show_default=True)
def cmd_batch(
    count: int,
    output: Path,
    seed_base: int,
    machines: int | None,
    operators: int | None,
    jobs: int | None,
    horizon_days: int,
    ops_per_job: tuple[int, int],
) -> None:
    """Génère un batch d'ateliers (un fichier JSON par atelier)."""
    if count < 1:
        click.echo("--count doit être >= 1", err=True)
        sys.exit(1)

    output.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Génération de {count} ateliers", total=count)
        for i in range(count):
            params = _build_params(
                seed=seed_base + i,
                machines=machines,
                jobs=jobs,
                operators=operators,
                horizon_days=horizon_days,
                ops_per_job=ops_per_job,
            )
            workshop = generate_workshop(params)
            _save_json(workshop, output / f"workshop_{i:04d}.json")
            progress.advance(task)

    elapsed = time.perf_counter() - t0
    console.print(f"\n[green]✓[/green] {count} ateliers générés en {elapsed:.2f}s")
    console.print(f"   Sortie : {output}")
    console.print(f"   Débit : {count / elapsed:.1f} ateliers/sec")


if __name__ == "__main__":
    cli()
