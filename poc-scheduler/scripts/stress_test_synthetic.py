"""Stress test Gate 0 part 2 — pipeline E2E sur ateliers synthétiques.

Génère N ateliers aux profils variés (small / medium / large), les convertit
en instances JSSP, lance le solveur avec un budget temps, et reporte les
statistiques d'agrégat.

Critère Gate 0 part 2 : solution faisable < 60s sur ≥ 80 % des cas avec
profils dans la plage 50-200 OF, 5-25 machines.

Usage :
    uv run python scripts/stress_test_synthetic.py run --count 30
    uv run python scripts/stress_test_synthetic.py run --count 50 --time-limit 60 --output stress.csv
    uv run python scripts/stress_test_synthetic.py run --profile medium --count 20
"""

from __future__ import annotations

import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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

from src.core.solver import JSSPSolver, SolverStatus, validate_schedule
from src.generators.workshop_generator import GenerationParams, generate_workshop
from src.loaders.synthetic_adapter import synthetic_to_jssp_instance

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "synthetic"

console = Console()


Profile = Literal["small", "medium", "large", "mixed"]


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    n_machines: tuple[int, int]
    n_jobs: tuple[int, int]
    n_operators: tuple[int, int]


PROFILES: dict[str, ProfileConfig] = {
    "small": ProfileConfig("small", (5, 8), (50, 80), (5, 10)),
    "medium": ProfileConfig("medium", (10, 15), (80, 150), (10, 20)),
    "large": ProfileConfig("large", (15, 25), (150, 200), (15, 30)),
}


@dataclass(frozen=True)
class StressRecord:
    seed: int
    profile: str
    n_machines: int
    n_jobs: int
    n_operations: int
    status: SolverStatus
    makespan: int | None
    solve_time_seconds: float
    feasible_under_budget: bool
    schedule_valid: bool


def _params_for_profile(seed: int, profile: ProfileConfig) -> GenerationParams:
    return GenerationParams(
        seed=seed,
        n_machines_min=profile.n_machines[0],
        n_machines_max=profile.n_machines[1],
        n_jobs_min=profile.n_jobs[0],
        n_jobs_max=profile.n_jobs[1],
        n_operators_min=profile.n_operators[0],
        n_operators_max=profile.n_operators[1],
    )


def _run_one(
    seed: int,
    profile: ProfileConfig,
    time_limit: float,
    num_workers: int,
) -> StressRecord:
    params = _params_for_profile(seed, profile)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    n_ops = sum(len(j.operations) for j in instance.jobs)

    solver = JSSPSolver(time_limit_seconds=time_limit, num_workers=num_workers)
    t0 = time.perf_counter()
    result = solver.solve(instance)
    elapsed = time.perf_counter() - t0

    feasible_under_budget = result.has_solution and elapsed <= time_limit + 1.0
    schedule_valid = False
    if result.has_solution:
        errors = validate_schedule(instance, result.schedule)
        schedule_valid = not errors

    return StressRecord(
        seed=seed,
        profile=profile.name,
        n_machines=instance.n_machines,
        n_jobs=instance.n_jobs,
        n_operations=n_ops,
        status=result.status,
        makespan=result.makespan,
        solve_time_seconds=elapsed,
        feasible_under_budget=feasible_under_budget,
        schedule_valid=schedule_valid,
    )


def _build_table() -> Table:
    table = Table(title="Stress test E2E — Gate 0 part 2")
    table.add_column("Seed", justify="right", style="dim")
    table.add_column("Profile", style="cyan")
    table.add_column("Mach", justify="right")
    table.add_column("OF", justify="right")
    table.add_column("Ops", justify="right")
    table.add_column("Makespan", justify="right")
    table.add_column("Time s", justify="right")
    table.add_column("Status")
    table.add_column("Feasible<budget")
    return table


def _add_row(table: Table, r: StressRecord) -> None:
    status_color = {
        SolverStatus.OPTIMAL: "bright_green",
        SolverStatus.FEASIBLE: "green",
        SolverStatus.INFEASIBLE: "red",
        SolverStatus.UNKNOWN: "yellow",
    }.get(r.status, "white")
    feas = "[green]✓[/]" if r.feasible_under_budget else "[red]✗[/]"
    table.add_row(
        str(r.seed),
        r.profile,
        str(r.n_machines),
        str(r.n_jobs),
        str(r.n_operations),
        "—" if r.makespan is None else str(r.makespan),
        f"{r.solve_time_seconds:.1f}",
        f"[{status_color}]{r.status.value}[/]",
        feas,
    )


def _summarize(records: list[StressRecord], time_limit: float) -> dict[str, float | int]:
    n = len(records)
    feasible = sum(1 for r in records if r.feasible_under_budget)
    valid = sum(1 for r in records if r.schedule_valid)
    optimal = sum(1 for r in records if r.status == SolverStatus.OPTIMAL)
    times = [r.solve_time_seconds for r in records]
    feasibility_rate = (feasible / n * 100.0) if n else 0.0
    return {
        "count": n,
        "feasible_under_budget": feasible,
        "feasibility_rate_percent": feasibility_rate,
        "schedule_valid_count": valid,
        "optimal_count": optimal,
        "mean_time_seconds": sum(times) / n if times else 0.0,
        "max_time_seconds": max(times) if times else 0.0,
        "time_limit_seconds": time_limit,
    }


def _write_csv(records: list[StressRecord], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "seed",
        "profile",
        "n_machines",
        "n_jobs",
        "n_operations",
        "status",
        "makespan",
        "solve_time_seconds",
        "feasible_under_budget",
        "schedule_valid",
    )
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "seed": r.seed,
                "profile": r.profile,
                "n_machines": r.n_machines,
                "n_jobs": r.n_jobs,
                "n_operations": r.n_operations,
                "status": r.status.value,
                "makespan": "" if r.makespan is None else r.makespan,
                "solve_time_seconds": f"{r.solve_time_seconds:.2f}",
                "feasible_under_budget": str(r.feasible_under_budget),
                "schedule_valid": str(r.schedule_valid),
            })
    return len(records)


@click.group()
def cli() -> None:
    """Stress test E2E — Gate 0 part 2."""


@cli.command("run")
@click.option("--count", default=30, type=int, show_default=True, help="Nombre d'ateliers à tester.")
@click.option(
    "--profile",
    type=click.Choice(["small", "medium", "large", "mixed"]),
    default="mixed",
    show_default=True,
    help="Profil unique ou mixed (rotation small/medium/large).",
)
@click.option("--time-limit", default=60.0, type=float, show_default=True, help="Budget par instance (s).")
@click.option("--num-workers", default=8, type=int, show_default=True)
@click.option("--seed-base", default=1000, type=int, show_default=True)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Chemin du CSV de sortie (optionnel).",
)
def cmd_run(
    count: int,
    profile: str,
    time_limit: float,
    num_workers: int,
    seed_base: int,
    output: Path | None,
) -> None:
    """Lance le stress test sur `count` ateliers et reporte les stats."""
    if count < 1:
        click.echo("--count doit être >= 1", err=True)
        sys.exit(1)

    profile_sequence: list[ProfileConfig]
    if profile == "mixed":
        rotation = [PROFILES["small"], PROFILES["medium"], PROFILES["large"]]
        profile_sequence = [rotation[i % 3] for i in range(count)]
    else:
        profile_sequence = [PROFILES[profile]] * count

    console.print(
        f"[bold]Stress test[/bold] — {count} ateliers · profil [cyan]{profile}[/cyan] · "
        f"budget {time_limit:.0f}s × {num_workers} workers"
    )
    console.print()

    records: list[StressRecord] = []
    table = _build_table()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Solving {count} ateliers", total=count)
        for i in range(count):
            seed = seed_base + i
            prof = profile_sequence[i]
            record = _run_one(seed, prof, time_limit, num_workers)
            records.append(record)
            _add_row(table, record)
            progress.advance(task)

    console.print(table)

    stats = _summarize(records, time_limit)
    rate = stats["feasibility_rate_percent"]
    rate_color = "bright_green" if rate >= 80.0 else ("yellow" if rate >= 60.0 else "red")
    console.print()
    console.print(
        f"[bold]Résumé[/bold] : "
        f"[{rate_color}]{stats['feasible_under_budget']}/{stats['count']} feasible<budget "
        f"({rate:.1f}%)[/] · "
        f"{stats['optimal_count']} OPTIMAL · "
        f"{stats['schedule_valid_count']} schedules valides · "
        f"temps moyen {stats['mean_time_seconds']:.1f}s · max {stats['max_time_seconds']:.1f}s"
    )

    gate_passed = rate >= 80.0
    if gate_passed:
        console.print("[bright_green]✓ Gate 0 part 2 PASSÉE — taux feasibility ≥ 80%[/]")
    else:
        console.print(
            f"[red]✗ Gate 0 part 2 NON PASSÉE — taux feasibility {rate:.1f}% < 80% requis[/]"
        )

    if output:
        n = _write_csv(records, output)
        console.print(f"\n[green]✓[/] {n} lignes écrites dans {output}")

    sys.exit(0 if gate_passed else 2)


if __name__ == "__main__":
    cli()
