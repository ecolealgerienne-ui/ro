"""CLI pour lancer des benchmarks Taillard et exporter les résultats.

Usage :
    uv run python scripts/run_taillard_benchmark.py solve ta01
    uv run python scripts/run_taillard_benchmark.py batch --range ta01-ta41 --time-limit 120 --output results.csv
    uv run python scripts/run_taillard_benchmark.py batch --instances ta01,ta11,ta21,ta31,ta41 --time-limit 120
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.core.solver import SolverStatus
from src.loaders.benchmark_runner import (
    BenchmarkRecord,
    run_batch,
    run_one,
    summarize,
    write_csv,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "taillard"

console = Console()


# ---------- Helpers d'affichage ----------


def _gap_color(gap: float | None) -> str:
    if gap is None:
        return "dim"
    if gap < 1.0:
        return "bright_green"
    if gap < 5.0:
        return "green"
    if gap < 10.0:
        return "yellow"
    return "red"


def _status_color(status: SolverStatus) -> str:
    return {
        SolverStatus.OPTIMAL: "bright_green",
        SolverStatus.FEASIBLE: "green",
        SolverStatus.INFEASIBLE: "red",
        SolverStatus.MODEL_INVALID: "red",
        SolverStatus.UNKNOWN: "yellow",
    }.get(status, "white")


def _build_table(title: str = "Résultats benchmark") -> Table:
    table = Table(title=title, show_lines=False)
    table.add_column("Instance", style="cyan", no_wrap=True)
    table.add_column("Jobs×Mach", justify="right")
    table.add_column("Best known", justify="right")
    table.add_column("Found", justify="right")
    table.add_column("Gap %", justify="right")
    table.add_column("Time s", justify="right")
    table.add_column("Status")
    return table


def _add_row(table: Table, record: BenchmarkRecord) -> None:
    gap_str = "—" if record.gap_percent is None else f"{record.gap_percent:+.2f}"
    found_str = "—" if record.found_makespan is None else str(record.found_makespan)
    bk_str = "—" if record.best_known_makespan is None else str(record.best_known_makespan)
    table.add_row(
        record.instance_name,
        f"{record.n_jobs}×{record.n_machines}",
        bk_str,
        found_str,
        f"[{_gap_color(record.gap_percent)}]{gap_str}[/]",
        f"{record.solve_time_seconds:.1f}",
        f"[{_status_color(record.status)}]{record.status.value}[/]",
    )


def _parse_range(spec: str) -> list[str]:
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


# ---------- Commandes ----------


@click.group()
def cli() -> None:
    """Benchmarks JSSP — solveur OR-Tools sur instances Taillard."""


@cli.command("solve")
@click.argument("name")
@click.option(
    "--time-limit", default=60.0, type=float, show_default=True, help="Budget temps (secondes)."
)
@click.option("--num-workers", default=8, type=int, show_default=True, help="Threads CP-SAT.")
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_DATA_DIR,
    show_default=True,
)
@click.option("--log/--no-log", default=False, help="Active les logs CP-SAT.")
def cmd_solve(
    name: str,
    time_limit: float,
    num_workers: int,
    data_dir: Path,
    log: bool,
) -> None:
    """Résout une instance unique et affiche le résultat."""
    console.print(
        f"[bold]Résolution de {name}[/bold] (budget {time_limit:.0f}s, {num_workers} workers)"
    )
    try:
        record = run_one(
            name,
            data_dir,
            time_limit_seconds=time_limit,
            num_workers=num_workers,
            log_search_progress=log,
        )
    except FileNotFoundError as e:
        console.print(f"[red]Erreur : {e}[/red]")
        sys.exit(1)

    table = _build_table(f"Instance {name}")
    _add_row(table, record)
    console.print(table)


@cli.command("batch")
@click.option("--instances", default=None, help="Liste séparée par virgule (ex: 'ta01,ta11,ta21').")
@click.option("--range", "range_spec", default=None, help="Range (ex: 'ta01-ta41').")
@click.option("--time-limit", default=60.0, type=float, show_default=True)
@click.option("--num-workers", default=8, type=int, show_default=True)
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_DATA_DIR,
    show_default=True,
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Chemin du CSV de sortie (optionnel).",
)
@click.option("--log/--no-log", default=False, help="Active les logs CP-SAT.")
def cmd_batch(
    instances: str | None,
    range_spec: str | None,
    time_limit: float,
    num_workers: int,
    data_dir: Path,
    output: Path | None,
    log: bool,
) -> None:
    """Lance le solveur sur un batch d'instances et exporte les résultats."""
    if instances and range_spec:
        raise click.UsageError("--instances et --range sont mutuellement exclusifs")
    if not instances and not range_spec:
        raise click.UsageError("Spécifier --instances ou --range")

    names = (
        _parse_range(range_spec)
        if range_spec
        else [s.strip() for s in (instances or "").split(",") if s.strip()]
    )
    console.print(
        f"[bold]Batch de {len(names)} instance(s)[/bold] — "
        f"budget {time_limit:.0f}s × {num_workers} workers"
    )
    console.print(f"Données : {data_dir}\n")

    table = _build_table()
    records: list[BenchmarkRecord] = []

    def _on_record(rec: BenchmarkRecord) -> None:
        records.append(rec)
        _add_row(table, rec)
        # Re-print whole table progressively (simple, robust)
        console.clear()
        console.print(f"[bold]Batch en cours[/bold] — {len(records)}/{len(names)} terminés")
        console.print(table)

    # Note : on_record append déjà, donc on n'append pas dans la valeur de retour
    completed = run_batch(
        names,
        data_dir,
        time_limit_seconds=time_limit,
        num_workers=num_workers,
        log_search_progress=log,
        on_record=_on_record,
    )

    # Récap final
    stats = summarize(completed)
    console.print()
    console.print(
        f"[bold]Résumé[/bold] : {stats['optimal_count']} OPTIMAL · "
        f"{stats['feasible_count']} FEASIBLE · "
        f"gap moyen {stats['mean_gap_percent']:.2f}% · "
        f"gap max {stats['max_gap_percent']:.2f}% · "
        f"temps moyen {stats['mean_time_seconds']:.1f}s"
    )

    if output:
        n_written = write_csv(completed, output)
        console.print(f"[green]✓[/green] {n_written} lignes écrites dans {output}")


if __name__ == "__main__":
    cli()
