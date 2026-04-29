"""Orchestration des benchmarks JSSP.

Charge des instances Taillard, lance le solveur avec un budget temps configurable,
calcule les gaps vs optima connus, exporte les résultats.

Sert principalement à l'étape 0.4 (validation gap < 5%) mais réutilisable
pour les benchmarks réguliers de non-régression.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Callable, Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.core.solver import JSSPSolver, SolverResult, SolverStatus
from src.loaders.taillard import load_taillard_instance

_logger = logging.getLogger(__name__)


CSV_FIELDS: tuple[str, ...] = (
    "instance",
    "n_jobs",
    "n_machines",
    "best_known",
    "found",
    "gap_percent",
    "time_seconds",
    "status",
    "objective_bound",
)


class BenchmarkRecord(BaseModel):
    """Une ligne de résultat de benchmark."""

    model_config = ConfigDict(frozen=True)

    instance_name: str
    n_jobs: int = Field(..., ge=1)
    n_machines: int = Field(..., ge=1)
    best_known_makespan: int | None = None
    found_makespan: int | None = None
    gap_percent: float | None = None
    status: SolverStatus
    solve_time_seconds: float = Field(..., ge=0.0)
    objective_bound: float | None = None

    @classmethod
    def from_result(
        cls,
        result: SolverResult,
        n_jobs: int,
        n_machines: int,
        best_known: int | None,
    ) -> BenchmarkRecord:
        """Construit un record depuis un `SolverResult` et ses métadonnées."""
        gap = result.gap_percent(best_known) if best_known is not None else None
        return cls(
            instance_name=result.instance_name,
            n_jobs=n_jobs,
            n_machines=n_machines,
            best_known_makespan=best_known,
            found_makespan=result.makespan,
            gap_percent=gap,
            status=result.status,
            solve_time_seconds=result.solve_time_seconds,
            objective_bound=result.objective_bound,
        )

    def as_csv_row(self) -> dict[str, str]:
        """Sérialisation pour `csv.DictWriter`."""
        return {
            "instance": self.instance_name,
            "n_jobs": str(self.n_jobs),
            "n_machines": str(self.n_machines),
            "best_known": "" if self.best_known_makespan is None else str(self.best_known_makespan),
            "found": "" if self.found_makespan is None else str(self.found_makespan),
            "gap_percent": "" if self.gap_percent is None else f"{self.gap_percent:.2f}",
            "time_seconds": f"{self.solve_time_seconds:.2f}",
            "status": self.status.value,
            "objective_bound": "" if self.objective_bound is None else f"{self.objective_bound:.2f}",
        }


def run_one(
    instance_name: str,
    data_dir: Path,
    *,
    time_limit_seconds: float = 60.0,
    num_workers: int = 8,
    log_search_progress: bool = False,
) -> BenchmarkRecord:
    """Charge une instance Taillard et la résout, retourne un `BenchmarkRecord`.

    Args:
        instance_name: Nom de l'instance (ex: "ta01").
        data_dir: Répertoire `data/taillard/`.
        time_limit_seconds: Budget temps max pour le solver.
        num_workers: Threads CP-SAT.
        log_search_progress: Active les logs CP-SAT.
    """
    instance = load_taillard_instance(instance_name, data_dir)
    solver = JSSPSolver(
        time_limit_seconds=time_limit_seconds,
        num_workers=num_workers,
        log_search_progress=log_search_progress,
    )
    result = solver.solve(instance)
    return BenchmarkRecord.from_result(
        result,
        n_jobs=instance.n_jobs,
        n_machines=instance.n_machines,
        best_known=instance.best_known_makespan,
    )


def run_batch(
    instance_names: Iterable[str],
    data_dir: Path,
    *,
    time_limit_seconds: float = 60.0,
    num_workers: int = 8,
    log_search_progress: bool = False,
    on_record: Callable[[BenchmarkRecord], None] | None = None,
) -> list[BenchmarkRecord]:
    """Lance le solveur sur une liste d'instances séquentiellement.

    Args:
        instance_names: Itérable de noms d'instances.
        data_dir: Répertoire des données Taillard.
        time_limit_seconds: Budget par instance.
        num_workers: Threads CP-SAT par instance.
        log_search_progress: Active les logs CP-SAT.
        on_record: Callback optionnel appelé après chaque résolution
            (utile pour affichage live).

    Returns:
        Liste des `BenchmarkRecord` dans l'ordre d'entrée.
    """
    records: list[BenchmarkRecord] = []
    for name in instance_names:
        try:
            record = run_one(
                name,
                data_dir,
                time_limit_seconds=time_limit_seconds,
                num_workers=num_workers,
                log_search_progress=log_search_progress,
            )
        except (FileNotFoundError, ValueError) as e:
            _logger.error("Échec sur %s : %s", name, e)
            raise
        records.append(record)
        if on_record is not None:
            on_record(record)
    return records


def write_csv(records: Iterable[BenchmarkRecord], output_path: Path) -> int:
    """Écrit les records au format CSV.

    Returns:
        Nombre de lignes écrites.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.as_csv_row())
            count += 1
    return count


def summarize(records: Iterable[BenchmarkRecord]) -> dict[str, float | int]:
    """Calcule des statistiques agrégées sur un batch.

    Returns:
        Dict avec `count`, `optimal_count`, `feasible_count`, `mean_gap_percent`,
        `max_gap_percent`, `mean_time_seconds`. Les statistiques sur le gap
        ignorent les records sans gap calculable (status non résolu ou
        `best_known_makespan` absent).
    """
    records_list = list(records)
    n = len(records_list)
    optimal = sum(1 for r in records_list if r.status == SolverStatus.OPTIMAL)
    feasible = sum(1 for r in records_list if r.status == SolverStatus.FEASIBLE)
    gaps = [r.gap_percent for r in records_list if r.gap_percent is not None]
    times = [r.solve_time_seconds for r in records_list]

    return {
        "count": n,
        "optimal_count": optimal,
        "feasible_count": feasible,
        "mean_gap_percent": sum(gaps) / len(gaps) if gaps else 0.0,
        "max_gap_percent": max(gaps) if gaps else 0.0,
        "mean_time_seconds": sum(times) / len(times) if times else 0.0,
    }
