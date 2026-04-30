"""Tests du solveur JSSP basique.

Stratégie :
1. Instance jouet 2×2 avec optimum calculable à la main → vérifie OPTIMAL exact.
2. Instance 3×3 (exemple OR-Tools job_shop) → vérifie OPTIMAL = 11.
3. Instance ta01 réelle (skipped si non téléchargée) → vérifie qu'on trouve
   une solution faisable rapidement avec budget court (vérification de gap
   réservée à l'étape 0.4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.models import Job, Machine, Operation, WorkshopInstance
from src.core.solver import (
    JSSPSolver,
    SolverResult,
    SolverStatus,
    validate_schedule,
)
from src.loaders.taillard import load_taillard_instance

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_DATA_DIR = REPO_ROOT / "data" / "taillard"


# ----- Helpers -----


def _make_instance(name: str, jobs_data: list[list[tuple[int, int]]]) -> WorkshopInstance:
    """Construit une `WorkshopInstance` depuis une liste de gammes (machine, durée)."""
    machine_ids: set[int] = set()
    jobs: list[Job] = []
    for j, gamme in enumerate(jobs_data):
        operations = [
            Operation(job_id=j, sequence_idx=k, machine_id=m, duration=d)
            for k, (m, d) in enumerate(gamme)
        ]
        machine_ids.update(m for m, _ in gamme)
        jobs.append(Job(job_id=j, operations=operations))
    machines = [Machine(machine_id=m) for m in sorted(machine_ids)]
    return WorkshopInstance(name=name, jobs=jobs, machines=machines)


# ----- Fixtures -----


@pytest.fixture
def trivial_2x2() -> WorkshopInstance:
    """2 jobs × 2 machines. Optimum = 5 (calculable à la main).

    Job 0 : M0(3) → M1(2)
    Job 1 : M1(2) → M0(2)

    Charge M0 = 5, charge M1 = 4, gamme la plus longue = 5 → LB = 5.
    Schedule optimal :
      M0 : J0(0–3), J1(3–5)
      M1 : J1(0–2), J0(3–5)
      makespan = 5.
    """
    return _make_instance(
        "trivial_2x2",
        [
            [(0, 3), (1, 2)],
            [(1, 2), (0, 2)],
        ],
    )


@pytest.fixture
def ortools_3x3() -> WorkshopInstance:
    """Exemple JSSP 3×3 documenté par OR-Tools (optimum = 11).

    Source : https://developers.google.com/optimization/scheduling/job_shop
    """
    return _make_instance(
        "ortools_3x3",
        [
            [(0, 3), (1, 2), (2, 2)],
            [(0, 2), (2, 1), (1, 4)],
            [(1, 4), (2, 3)],
        ],
    )


# ----- Tests sur instances jouet -----


def test_solver_init_validates_args() -> None:
    with pytest.raises(ValueError):
        JSSPSolver(time_limit_seconds=0)
    with pytest.raises(ValueError):
        JSSPSolver(num_workers=0)


def test_solve_trivial_2x2_optimal(trivial_2x2: WorkshopInstance) -> None:
    solver = JSSPSolver(time_limit_seconds=10, num_workers=4)
    result = solver.solve(trivial_2x2)
    assert result.status == SolverStatus.OPTIMAL
    assert result.makespan == 5
    assert result.has_solution
    errors = validate_schedule(trivial_2x2, result.schedule)
    assert not errors, f"Schedule invalide : {errors}"


def test_solve_ortools_3x3_optimal(ortools_3x3: WorkshopInstance) -> None:
    solver = JSSPSolver(time_limit_seconds=10, num_workers=4)
    result = solver.solve(ortools_3x3)
    assert result.status == SolverStatus.OPTIMAL
    assert result.makespan == 11
    errors = validate_schedule(ortools_3x3, result.schedule)
    assert not errors, f"Schedule invalide : {errors}"


def test_schedule_assignments_complete(ortools_3x3: WorkshopInstance) -> None:
    solver = JSSPSolver(time_limit_seconds=10, num_workers=4)
    result = solver.solve(ortools_3x3)
    expected_op_count = sum(len(j.operations) for j in ortools_3x3.jobs)
    assert len(result.schedule) == expected_op_count


def test_gap_percent_helper() -> None:
    result = SolverResult(
        instance_name="x",
        status=SolverStatus.OPTIMAL,
        makespan=110,
        objective_bound=100.0,
        schedule=[],
        solve_time_seconds=0.5,
    )
    assert result.gap_percent(100) == pytest.approx(10.0)
    assert result.gap_percent(0) is None

    no_solution = SolverResult(
        instance_name="x",
        status=SolverStatus.UNKNOWN,
        makespan=None,
        objective_bound=None,
        schedule=[],
        solve_time_seconds=0.5,
    )
    assert no_solution.gap_percent(100) is None


# ----- Validation helper -----


def test_validate_schedule_detects_machine_overlap(trivial_2x2: WorkshopInstance) -> None:
    from src.core.solver import ScheduleAssignment

    bad_schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=3),
        ScheduleAssignment(job_id=0, sequence_idx=1, machine_id=1, start=3, end=5),
        ScheduleAssignment(job_id=1, sequence_idx=0, machine_id=1, start=0, end=2),
        ScheduleAssignment(job_id=1, sequence_idx=1, machine_id=0, start=2, end=4),
    ]
    errors = validate_schedule(trivial_2x2, bad_schedule)
    assert any("Machine 0" in e and "chevauchement" in e for e in errors)


def test_validate_schedule_detects_precedence_violation(trivial_2x2: WorkshopInstance) -> None:
    from src.core.solver import ScheduleAssignment

    bad_schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=5, end=8),
        ScheduleAssignment(job_id=0, sequence_idx=1, machine_id=1, start=0, end=2),
        ScheduleAssignment(job_id=1, sequence_idx=0, machine_id=1, start=2, end=4),
        ScheduleAssignment(job_id=1, sequence_idx=1, machine_id=0, start=8, end=10),
    ]
    errors = validate_schedule(trivial_2x2, bad_schedule)
    assert any("Précédence" in e for e in errors)


# ----- Smoke test sur ta01 réelle -----


@pytest.mark.slow
def test_solver_finds_solution_on_ta01() -> None:
    """Smoke test : ta01 (15×15) doit être résolvable en moins de 30s.

    On vérifie qu'on obtient au moins FEASIBLE (gap < 5% sera testé en 0.4).
    """
    path = REAL_DATA_DIR / "ta01"
    if not path.exists():
        pytest.skip(
            "ta01 non téléchargé — lancer "
            "`uv run python scripts/download_benchmarks.py taillard --range ta01-ta01`"
        )
    instance = load_taillard_instance("ta01", REAL_DATA_DIR)
    solver = JSSPSolver(time_limit_seconds=30, num_workers=4)
    result = solver.solve(instance)
    assert result.has_solution, f"Status inattendu : {result.status}"
    assert result.makespan is not None and result.makespan > 0
    # Sanity : optimum prouvé ta01 = 1231 ; on accepte tout makespan >= 1231
    assert result.makespan >= 1231
    errors = validate_schedule(instance, result.schedule)
    assert not errors, f"Schedule ta01 invalide : {errors}"
