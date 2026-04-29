"""Tests d'intégration E2E : générateur → adaptateur → solveur → validation.

Tests rapides sur de petites instances. Le stress test taille réelle (Gate 0
part 2) est dans `scripts/stress_test_synthetic.py` (run manuel).
"""

from __future__ import annotations

import time

import pytest

from src.core.solver import JSSPSolver, SolverStatus, validate_schedule
from src.generators.workshop_generator import GenerationParams, generate_workshop
from src.loaders.synthetic_adapter import synthetic_to_jssp_instance


def _e2e(params: GenerationParams, time_limit: float = 10.0, num_workers: int = 4):
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    solver = JSSPSolver(time_limit_seconds=time_limit, num_workers=num_workers)
    result = solver.solve(instance)
    return workshop, instance, result


def test_e2e_small_workshop_finds_feasible_solution() -> None:
    """Atelier 5 machines × 10 OF — doit trouver une solution rapidement."""
    params = GenerationParams(
        seed=42,
        n_machines_min=5,
        n_machines_max=5,
        n_jobs_min=10,
        n_jobs_max=10,
        n_operators_min=3,
        n_operators_max=3,
    )
    _, instance, result = _e2e(params, time_limit=10.0)
    assert result.has_solution, f"Pas de solution sur instance 5×10 : {result.status}"
    errors = validate_schedule(instance, result.schedule)
    assert not errors, f"Schedule invalide : {errors}"


def test_e2e_medium_workshop_finds_solution() -> None:
    """Atelier 10 machines × 30 OF — taille intermédiaire."""
    params = GenerationParams(
        seed=42,
        n_machines_min=10,
        n_machines_max=10,
        n_jobs_min=30,
        n_jobs_max=30,
    )
    _, instance, result = _e2e(params, time_limit=15.0, num_workers=4)
    assert result.has_solution, f"Pas de solution sur instance 10×30 : {result.status}"
    errors = validate_schedule(instance, result.schedule)
    assert not errors


def test_e2e_solution_respects_durations() -> None:
    params = GenerationParams(
        seed=42,
        n_machines_min=5,
        n_machines_max=5,
        n_jobs_min=10,
        n_jobs_max=10,
    )
    _, instance, result = _e2e(params, time_limit=10.0)
    assert result.has_solution
    by_op = {(a.job_id, a.sequence_idx): a for a in result.schedule}
    for job in instance.jobs:
        for op in job.operations:
            assignment = by_op[(job.job_id, op.sequence_idx)]
            assert assignment.end - assignment.start == op.duration


def test_e2e_machines_used_match_workshop() -> None:
    params = GenerationParams(
        seed=42, n_machines_min=8, n_machines_max=8, n_jobs_min=15, n_jobs_max=15
    )
    _, instance, result = _e2e(params, time_limit=10.0)
    assert result.has_solution
    machine_ids = {m.machine_id for m in instance.machines}
    for assignment in result.schedule:
        assert assignment.machine_id in machine_ids


def test_e2e_makespan_is_positive() -> None:
    params = GenerationParams(
        seed=42, n_machines_min=5, n_machines_max=5, n_jobs_min=10, n_jobs_max=10
    )
    _, _, result = _e2e(params, time_limit=10.0)
    assert result.has_solution
    assert result.makespan is not None and result.makespan > 0


@pytest.mark.slow
def test_e2e_realistic_workshop_under_60_seconds() -> None:
    """Atelier représentatif de l'ICP (15 machines × 80 OF) doit trouver une
    solution faisable en moins de 60s.

    C'est un mini-test du Gate 0 part 2 — la validation complète est dans
    le stress test (50 ateliers).
    """
    params = GenerationParams(
        seed=42,
        n_machines_min=15,
        n_machines_max=15,
        n_jobs_min=80,
        n_jobs_max=80,
    )
    t0 = time.perf_counter()
    _, instance, result = _e2e(params, time_limit=60.0, num_workers=8)
    elapsed = time.perf_counter() - t0
    assert result.has_solution, (
        f"Pas de solution sur 15×80 en 60s : {result.status} "
        f"(elapsed {elapsed:.1f}s)"
    )
    errors = validate_schedule(instance, result.schedule)
    assert not errors
