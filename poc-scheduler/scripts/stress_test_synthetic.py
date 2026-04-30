"""Stress test E2E — pipeline générateur → adaptateur → solveur.

Étape 0.7 : valide Gate 0 part 2 (≥ 80 % feasibility en < 60s sur ateliers
50-200 OF, 5-25 machines, JSSP de base).

Étape 1.1d : ajoute la dimension `mode` (basic / setup / operator / shared /
full) pour mesurer l'impact des patterns industriels sur la performance,
et un sous-commande `compare` pour exécuter tous les modes sur les mêmes
seeds et produire un tableau comparatif.

Usage :
    uv run python scripts/stress_test_synthetic.py run --count 30
    uv run python scripts/stress_test_synthetic.py run --mode full --count 10
    uv run python scripts/stress_test_synthetic.py compare --count 10 --time-limit 60
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
from src.verticals.mech_workshop.adapter import synthetic_to_jssp_instance
from src.verticals.mech_workshop.generator import GenerationParams, generate_workshop

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "synthetic"

console = Console()


Profile = Literal["small", "medium", "large", "mixed"]
Mode = Literal["basic", "setup", "operator", "shared", "full"]


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


# Mode = (enable_setup, enable_operators, enable_shared_resources)
MODE_FLAGS: dict[str, tuple[bool, bool, bool]] = {
    "basic": (False, False, False),
    "setup": (True, False, False),
    "operator": (False, True, False),
    "shared": (False, False, True),
    "full": (True, True, True),
}


@dataclass(frozen=True)
class StressRecord:
    seed: int
    profile: str
    mode: str
    n_machines: int
    n_jobs: int
    n_operations: int
    status: SolverStatus
    makespan: int | None
    solve_time_seconds: float
    feasible_under_budget: bool
    schedule_valid: bool
    patterns_count: int


def _params_for_profile(seed: int, profile: ProfileConfig) -> GenerationParams:
    return GenerationParams(
        seed=seed,
        n_machines_min=profile.n_machines[0],
        n_machines_max=profile.n_machines[1],
        n_jobs_min=profile.n_jobs[0],
        n_jobs_max=profile.n_jobs[1],
        n_operators_min=profile.n_operators[0],
        n_operators_max=profile.n_operators[1],
        shared_resource_probability=1.0,  # toujours injecter pour mode "shared"/"full"
    )


def _run_one(
    seed: int,
    profile: ProfileConfig,
    mode: str,
    time_limit: float,
    num_workers: int,
) -> StressRecord:
    params = _params_for_profile(seed, profile)
    workshop = generate_workshop(params)
    enable_setup, enable_operators, enable_shared = MODE_FLAGS[mode]
    instance = synthetic_to_jssp_instance(
        workshop,
        enable_setup=enable_setup,
        enable_operators=enable_operators,
        enable_shared_resources=enable_shared,
    )
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
        mode=mode,
        n_machines=instance.n_machines,
        n_jobs=instance.n_jobs,
        n_operations=n_ops,
        status=result.status,
        makespan=result.makespan,
        solve_time_seconds=elapsed,
        feasible_under_budget=feasible_under_budget,
        schedule_valid=schedule_valid,
        patterns_count=len(result.patterns_applied),
    )


def _build_table(title: str = "Stress test E2E") -> Table:
    table = Table(title=title)
    table.add_column("Seed", justify="right", style="dim")
    table.add_column("Profile", style="cyan")
    table.add_column("Mode", style="magenta")
    table.add_column("Mach", justify="right")
    table.add_column("OF", justify="right")
    table.add_column("Ops", justify="right")
    table.add_column("Makespan", justify="right")
    table.add_column("Time s", justify="right")
    table.add_column("Status")
    table.add_column("OK")
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
        r.mode,
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
        "mode",
        "n_machines",
        "n_jobs",
        "n_operations",
        "status",
        "makespan",
        "solve_time_seconds",
        "feasible_under_budget",
        "schedule_valid",
        "patterns_count",
    )
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "seed": r.seed,
                    "profile": r.profile,
                    "mode": r.mode,
                    "n_machines": r.n_machines,
                    "n_jobs": r.n_jobs,
                    "n_operations": r.n_operations,
                    "status": r.status.value,
                    "makespan": "" if r.makespan is None else r.makespan,
                    "solve_time_seconds": f"{r.solve_time_seconds:.2f}",
                    "feasible_under_budget": str(r.feasible_under_budget),
                    "schedule_valid": str(r.schedule_valid),
                    "patterns_count": r.patterns_count,
                }
            )
    return len(records)


def _resolve_profile_sequence(profile: str, count: int) -> list[ProfileConfig]:
    if profile == "mixed":
        rotation = [PROFILES["small"], PROFILES["medium"], PROFILES["large"]]
        return [rotation[i % 3] for i in range(count)]
    return [PROFILES[profile]] * count


@click.group()
def cli() -> None:
    """Stress test E2E — pipeline générateur → solveur, avec modes pour mesurer l'impact des patterns."""


@cli.command("run")
@click.option("--count", default=30, type=int, show_default=True)
@click.option(
    "--profile",
    type=click.Choice(["small", "medium", "large", "mixed"]),
    default="mixed",
    show_default=True,
)
@click.option(
    "--mode",
    type=click.Choice(list(MODE_FLAGS.keys())),
    default="basic",
    show_default=True,
    help="basic = JSSP nu · setup/operator/shared = un pattern à la fois · full = tous les patterns",
)
@click.option("--time-limit", default=60.0, type=float, show_default=True)
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
    mode: str,
    time_limit: float,
    num_workers: int,
    seed_base: int,
    output: Path | None,
) -> None:
    """Lance le stress test sur `count` ateliers dans un mode donné."""
    if count < 1:
        click.echo("--count doit être >= 1", err=True)
        sys.exit(1)

    profile_sequence = _resolve_profile_sequence(profile, count)
    console.print(
        f"[bold]Stress test[/bold] — {count} ateliers · profil [cyan]{profile}[/cyan] · "
        f"mode [magenta]{mode}[/magenta] · budget {time_limit:.0f}s × {num_workers} workers"
    )
    console.print()

    records: list[StressRecord] = []
    table = _build_table(f"Stress test E2E — mode {mode}")

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
            record = _run_one(seed, prof, mode, time_limit, num_workers)
            records.append(record)
            _add_row(table, record)
            progress.advance(task)

    console.print(table)

    stats = _summarize(records, time_limit)
    rate = stats["feasibility_rate_percent"]
    rate_color = "bright_green" if rate >= 80.0 else ("yellow" if rate >= 60.0 else "red")
    console.print()
    console.print(
        f"[bold]Résumé mode {mode}[/bold] : "
        f"[{rate_color}]{stats['feasible_under_budget']}/{stats['count']} feasible<budget "
        f"({rate:.1f}%)[/] · "
        f"{stats['optimal_count']} OPTIMAL · "
        f"{stats['schedule_valid_count']} schedules valides · "
        f"temps moyen {stats['mean_time_seconds']:.1f}s · max {stats['max_time_seconds']:.1f}s"
    )

    gate_passed = rate >= 80.0
    if gate_passed:
        console.print("[bright_green]✓ Seuil 80% atteint[/]")
    else:
        console.print(f"[red]✗ Seuil 80% non atteint ({rate:.1f}%)[/]")

    if output:
        n = _write_csv(records, output)
        console.print(f"\n[green]✓[/] {n} lignes écrites dans {output}")

    sys.exit(0 if gate_passed else 2)


@cli.command("compare")
@click.option("--count", default=10, type=int, show_default=True, help="Ateliers par mode.")
@click.option(
    "--profile",
    type=click.Choice(["small", "medium", "large", "mixed"]),
    default="mixed",
    show_default=True,
)
@click.option("--time-limit", default=60.0, type=float, show_default=True)
@click.option("--num-workers", default=8, type=int, show_default=True)
@click.option("--seed-base", default=2000, type=int, show_default=True)
@click.option(
    "--modes",
    default="basic,setup,operator,shared,full",
    show_default=True,
    help="Liste des modes à comparer (séparés par virgule).",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="CSV cumulé tous modes (optionnel).",
)
def cmd_compare(
    count: int,
    profile: str,
    time_limit: float,
    num_workers: int,
    seed_base: int,
    modes: str,
    output: Path | None,
) -> None:
    """Exécute plusieurs modes sur les MÊMES seeds et compare l'impact."""
    mode_list = [m.strip() for m in modes.split(",") if m.strip()]
    invalid = [m for m in mode_list if m not in MODE_FLAGS]
    if invalid:
        click.echo(f"Modes inconnus : {invalid}. Disponibles : {list(MODE_FLAGS)}", err=True)
        sys.exit(1)

    profile_sequence = _resolve_profile_sequence(profile, count)
    total_runs = count * len(mode_list)

    console.print(
        f"[bold]Comparaison[/bold] — {count} ateliers × {len(mode_list)} modes = {total_runs} runs · "
        f"profil [cyan]{profile}[/cyan] · budget {time_limit:.0f}s × {num_workers} workers"
    )
    console.print(f"Modes : {', '.join(mode_list)}")
    console.print()

    all_records: list[StressRecord] = []
    stats_per_mode: dict[str, dict[str, float | int]] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Total {total_runs} runs", total=total_runs)
        for mode in mode_list:
            mode_records: list[StressRecord] = []
            for i in range(count):
                seed = seed_base + i  # mêmes seeds entre modes
                prof = profile_sequence[i]
                record = _run_one(seed, prof, mode, time_limit, num_workers)
                mode_records.append(record)
                all_records.append(record)
                progress.advance(task)
            stats_per_mode[mode] = _summarize(mode_records, time_limit)

    # Tableau comparatif
    summary_table = Table(title=f"Impact des patterns sur {count} ateliers ({profile})")
    summary_table.add_column("Mode", style="magenta")
    summary_table.add_column("Feasible", justify="right")
    summary_table.add_column("Rate %", justify="right")
    summary_table.add_column("OPTIMAL", justify="right")
    summary_table.add_column("Mean time s", justify="right")
    summary_table.add_column("Max time s", justify="right")

    for mode in mode_list:
        s = stats_per_mode[mode]
        rate = float(s["feasibility_rate_percent"])
        rate_color = "bright_green" if rate >= 80.0 else ("yellow" if rate >= 60.0 else "red")
        summary_table.add_row(
            mode,
            f"{s['feasible_under_budget']}/{s['count']}",
            f"[{rate_color}]{rate:.1f}[/]",
            str(s["optimal_count"]),
            f"{s['mean_time_seconds']:.1f}",
            f"{s['max_time_seconds']:.1f}",
        )

    console.print()
    console.print(summary_table)

    # Verdict global : tous les modes >= 80% requis
    all_pass = all(float(stats_per_mode[m]["feasibility_rate_percent"]) >= 80.0 for m in mode_list)
    console.print()
    if all_pass:
        console.print("[bright_green]✓ Tous les modes ≥ 80% feasibility — Phase 1.1 validée[/]")
    else:
        weak = [
            f"{m} ({stats_per_mode[m]['feasibility_rate_percent']:.1f}%)"
            for m in mode_list
            if float(stats_per_mode[m]["feasibility_rate_percent"]) < 80.0
        ]
        console.print(f"[yellow]⚠ Modes sous 80% : {', '.join(weak)}[/]")
        console.print(
            "Cela ne signifie pas un échec — c'est l'effet attendu de la complexité ajoutée."
        )
        console.print("Décision en 1.1d : optimiser les patterns coûteux ou ajuster le scope.")

    if output:
        n = _write_csv(all_records, output)
        console.print(f"\n[green]✓[/] {n} lignes écrites dans {output}")

    sys.exit(0 if all_pass else 2)


if __name__ == "__main__":
    cli()
