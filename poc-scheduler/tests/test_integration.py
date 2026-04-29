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


# ---------- Étape 1.1c : intégration des patterns au solveur ----------


def test_e2e_with_full_patterns_active() -> None:
    """Atelier moyen avec setup + operators + shared resources actifs."""
    params = GenerationParams(
        seed=42,
        n_machines_min=8,
        n_machines_max=8,
        n_jobs_min=20,
        n_jobs_max=20,
        n_operators_min=4,
        n_operators_max=4,
        shared_resource_probability=1.0,
    )
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert instance.has_setup_constraints
    assert instance.has_operator_constraints
    assert instance.has_shared_resources
    solver = JSSPSolver(time_limit_seconds=30.0, num_workers=4)
    result = solver.solve(instance)
    assert result.has_solution, f"Pas de solution avec patterns complets : {result.status}"
    errors = validate_schedule(instance, result.schedule)
    assert not errors


def test_solver_records_patterns_applied() -> None:
    """Le SolverResult expose la liste des patterns activés."""
    params = GenerationParams(seed=42, n_machines_min=5, n_machines_max=5, n_jobs_min=10, n_jobs_max=10)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    solver = JSSPSolver(time_limit_seconds=10.0, num_workers=2)
    result = solver.solve(instance)
    assert "precedence_in_job" in result.patterns_applied
    assert "no_overlap_machine" in result.patterns_applied
    assert "makespan_objective" in result.patterns_applied
    if instance.has_setup_constraints:
        assert "no_overlap_with_setup" in result.patterns_applied
    if instance.has_operator_constraints:
        assert "qualified_operator" in result.patterns_applied


def test_solver_skips_patterns_when_disabled() -> None:
    """Avec adaptateur en mode dégradé, seuls NoOverlap+Precedence+Makespan."""
    params = GenerationParams(seed=42, n_machines_min=5, n_machines_max=5, n_jobs_min=10, n_jobs_max=10)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(
        workshop,
        enable_setup=False,
        enable_operators=False,
        enable_shared_resources=False,
    )
    solver = JSSPSolver(time_limit_seconds=10.0, num_workers=2)
    result = solver.solve(instance)
    assert result.has_solution
    assert "no_overlap_with_setup" not in result.patterns_applied
    assert "qualified_operator" not in result.patterns_applied
    assert "shared_resource_exclusion" not in result.patterns_applied


def test_e2e_setup_only_increases_or_equal_makespan() -> None:
    """Activer setup ne peut pas réduire le makespan vs sans setup."""
    params = GenerationParams(
        seed=42, n_machines_min=5, n_machines_max=5, n_jobs_min=15, n_jobs_max=15
    )
    workshop = generate_workshop(params)

    instance_no_setup = synthetic_to_jssp_instance(
        workshop, enable_setup=False, enable_operators=False, enable_shared_resources=False
    )
    instance_with_setup = synthetic_to_jssp_instance(
        workshop, enable_setup=True, enable_operators=False, enable_shared_resources=False
    )
    solver = JSSPSolver(time_limit_seconds=20.0, num_workers=4)
    r1 = solver.solve(instance_no_setup)
    r2 = solver.solve(instance_with_setup)
    assert r1.has_solution and r2.has_solution
    assert r2.makespan is not None and r1.makespan is not None
    assert r2.makespan >= r1.makespan


def test_e2e_with_unavailability() -> None:
    """Atelier avec une plage d'indisponibilité explicite — solveur la respecte."""
    from src.core.models import MachineUnavailabilitySpec

    params = GenerationParams(seed=42, n_machines_min=5, n_machines_max=5, n_jobs_min=8, n_jobs_max=8)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)

    # Bloquer la machine 0 entre 100 et 200
    enriched = instance.model_copy(
        update={
            "machine_unavailability": [
                MachineUnavailabilitySpec(machine_id=0, periods=[(100, 200)])
            ]
        }
    )
    solver = JSSPSolver(time_limit_seconds=15.0, num_workers=4)
    result = solver.solve(enriched)
    assert result.has_solution
    # Aucune opération sur M0 ne doit chevaucher [100, 200]
    for a in result.schedule:
        if a.machine_id == 0:
            assert a.end <= 100 or a.start >= 200, (
                f"Op {(a.job_id, a.sequence_idx)} sur M0 chevauche [100,200] : [{a.start}, {a.end}]"
            )


def test_solve_taillard_still_works_after_refactor() -> None:
    """Sanity check : les instances JSSP nues (sans champs industriels) restent OK."""
    from pathlib import Path

    from src.loaders.taillard import load_taillard_instance

    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data" / "taillard"
    if not (data_dir / "ta01").exists():
        pytest.skip("ta01 non téléchargé")
    instance = load_taillard_instance("ta01", data_dir)
    assert not instance.has_setup_constraints
    assert not instance.has_operator_constraints
    assert not instance.has_shared_resources
    solver = JSSPSolver(time_limit_seconds=15.0, num_workers=4)
    result = solver.solve(instance)
    assert result.has_solution
    assert result.makespan is not None and result.makespan >= 1231
