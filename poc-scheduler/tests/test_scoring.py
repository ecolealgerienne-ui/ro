"""Tests du module `src.core.scoring` (engine generique).

Couvre :
- Statut OPTIMAL -> score eleve
- Statut INFEASIBLE -> score 0
- Gate `validate_schedule` qui echoue -> score 0 (overrides toutes metriques)
- best_known_makespan absent -> gap a 0.5 par defaut
- Poids absents/zeros -> score 0 + note
- Calcul de machine_utilization (analytique)
- Integration avec un golden case (cas baseline_001 : OPTIMAL, util ~ 100 %)
"""

from __future__ import annotations

from src.core.models import Job, Machine, Operation, WorkshopInstance
from src.core.scoring import (
    METRIC_NAMES,
    ConfidenceScore,
    score_solver_result,
)
from src.core.solver import (
    JSSPSolver,
    ScheduleAssignment,
    SolverResult,
    SolverStatus,
)
from src.verticals.mech_workshop import MECH_CONFIDENCE_WEIGHTS

WEIGHTS_FLAT = dict.fromkeys(METRIC_NAMES, 1.0)


def _trivial_instance(best_known: int | None = None) -> WorkshopInstance:
    return WorkshopInstance(
        name="trivial",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5),
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
        best_known_makespan=best_known,
    )


def _valid_result(makespan: int = 5, status: SolverStatus = SolverStatus.OPTIMAL) -> SolverResult:
    return SolverResult(
        instance_name="trivial",
        status=status,
        makespan=makespan,
        schedule=[ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5)],
        solve_time_seconds=0.1,
    )


# ---------- Cas nominal ----------


def test_optimal_with_perfect_metrics_yields_high_score() -> None:
    instance = _trivial_instance(best_known=5)
    result = _valid_result()
    score = score_solver_result(instance, result, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    assert score.gate_passed
    assert score.overall > 0.9


def test_metrics_have_expected_names() -> None:
    instance = _trivial_instance()
    result = _valid_result()
    score = score_solver_result(instance, result, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    names = {m.name for m in score.metrics}
    assert names == set(METRIC_NAMES)


# ---------- Statuts non OPTIMAL ----------


def test_infeasible_status_yields_zero() -> None:
    instance = _trivial_instance()
    result = SolverResult(
        instance_name="trivial",
        status=SolverStatus.INFEASIBLE,
        makespan=None,
        schedule=[],
        solve_time_seconds=0.1,
    )
    score = score_solver_result(instance, result, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    assert not score.gate_passed
    assert score.overall == 0.0


def test_feasible_lower_than_optimal() -> None:
    instance = _trivial_instance(best_known=5)
    optimal = _valid_result(status=SolverStatus.OPTIMAL)
    feasible = _valid_result(status=SolverStatus.FEASIBLE)
    s_optimal = score_solver_result(instance, optimal, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    s_feasible = score_solver_result(instance, feasible, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    assert s_optimal.overall > s_feasible.overall


# ---------- Gate validate_schedule ----------


def test_gate_failure_overrides_metrics() -> None:
    """Un statut OPTIMAL avec une schedule incoherente doit donner score 0."""
    instance = _trivial_instance(best_known=5)
    bogus = SolverResult(
        instance_name="trivial",
        status=SolverStatus.OPTIMAL,
        makespan=5,
        schedule=[
            ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=999),
        ],
        solve_time_seconds=0.1,
    )
    score = score_solver_result(instance, bogus, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    assert not score.gate_passed
    assert score.overall == 0.0
    assert any("validate_schedule" in n for n in score.notes)


# ---------- Cas best_known absent ----------


def test_no_best_known_yields_neutral_gap() -> None:
    instance = _trivial_instance(best_known=None)
    result = _valid_result()
    score = score_solver_result(instance, result, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    gap = next(m for m in score.metrics if m.name == "gap_to_best_known")
    assert gap.normalized == 0.5
    assert gap.raw_value == -1.0
    assert any("best_known_makespan" in n for n in score.notes)


# ---------- Cas degradés ----------


def test_zero_total_weight_yields_zero_score() -> None:
    instance = _trivial_instance(best_known=5)
    result = _valid_result()
    score = score_solver_result(instance, result, weights={}, time_limit_s=60.0)
    assert score.gate_passed
    assert score.overall == 0.0
    assert any("poids" in n for n in score.notes)


def test_unknown_weight_keys_are_ignored() -> None:
    instance = _trivial_instance(best_known=5)
    result = _valid_result()
    weights = {"machine_utilization": 1.0, "unknown_metric": 99.0}
    score = score_solver_result(instance, result, weights=weights, time_limit_s=60.0)
    assert score.gate_passed
    util = next(m for m in score.metrics if m.name == "machine_utilization")
    assert util.weight == 1.0


# ---------- Machine utilization ----------


def test_full_utilization_when_perfect_packing() -> None:
    instance = _trivial_instance()
    result = _valid_result(makespan=5)
    score = score_solver_result(instance, result, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    util = next(m for m in score.metrics if m.name == "machine_utilization")
    assert util.normalized == 1.0


def test_low_utilization_when_machines_idle() -> None:
    instance = WorkshopInstance(
        name="two_machines_one_op",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            ),
        ],
        machines=[Machine(machine_id=0), Machine(machine_id=1)],
    )
    result = SolverResult(
        instance_name="two_machines_one_op",
        status=SolverStatus.OPTIMAL,
        makespan=5,
        schedule=[ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5)],
        solve_time_seconds=0.1,
    )
    score = score_solver_result(instance, result, weights=WEIGHTS_FLAT, time_limit_s=60.0)
    util = next(m for m in score.metrics if m.name == "machine_utilization")
    assert util.normalized == 0.5  # 1 machine sur 2 occupee


# ---------- Integration solveur reel ----------


def test_integration_with_real_solver_on_baseline_3x3() -> None:
    """Cas reel : le 3x3 du golden case baseline_001, optimum = 9, util attendue = 1.0."""
    instance = WorkshopInstance(
        name="integration_baseline_3x3",
        jobs=[
            Job(
                job_id=j,
                operations=[
                    Operation(
                        job_id=j,
                        sequence_idx=i,
                        machine_id=(j + i) % 3,
                        duration=3,
                    )
                    for i in range(3)
                ],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=m) for m in range(3)],
        best_known_makespan=9,
    )
    solver = JSSPSolver(time_limit_seconds=10.0)
    result = solver.solve(instance)
    score = score_solver_result(
        instance, result, weights=MECH_CONFIDENCE_WEIGHTS, time_limit_s=10.0
    )
    assert score.gate_passed
    assert score.overall > 0.85
    assert isinstance(score, ConfidenceScore)


# ---------- Verticale méca : poids cohérents ----------


def test_mech_weights_sum_to_one() -> None:
    """Les poids meca somment a 1.0 (par convention de calibration)."""
    assert abs(sum(MECH_CONFIDENCE_WEIGHTS.values()) - 1.0) < 1e-9


def test_mech_weights_cover_all_metrics() -> None:
    assert set(MECH_CONFIDENCE_WEIGHTS.keys()) == set(METRIC_NAMES)
