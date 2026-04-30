"""Tests du pipeline complet `src.core.pipeline`.

Couvre :
- Pipeline ACCEPT sur baseline 3x3 (cas reel)
- Pipeline REJECT sur INFEASIBLE (circuit breaker non SOLVED)
- Pipeline REJECT sur EXHAUSTED (monkeypatch)
- Pipeline REJECT si simulation verdict == REJECT
- Pipeline WARN si simulation verdict == WARN, sinon ACCEPT
- Le pipeline expose simulation et score = None quand non SOLVED

Test E2E (Gate 1) :
- 20 ateliers meca synthetiques, aucune erreur silencieuse :
  pour chaque decision ACCEPT, validate_schedule retourne 0 erreur.
"""

from __future__ import annotations

import pytest

from src.core.circuit_breaker import CircuitBreakerOutcome
from src.core.models import Job, Machine, MachineUnavailabilitySpec, Operation, WorkshopInstance
from src.core.pipeline import (
    PipelineDecisionKind,
    PipelineReport,
    run_pipeline,
)
from src.core.solver import (
    JSSPSolver,
    ScheduleAssignment,
    SolverResult,
    SolverStatus,
    validate_schedule,
)
from src.verticals.mech_workshop import (
    MECH_CONFIDENCE_WEIGHTS,
    MECH_SIMULATION_THRESHOLDS,
    GenerationParams,
    generate_workshop,
    synthetic_to_jssp_instance,
)

CFG = {
    "confidence_weights": MECH_CONFIDENCE_WEIGHTS,
    "simulation_thresholds": MECH_SIMULATION_THRESHOLDS,
    "time_budgets_s": (5.0,),
}


def _baseline_3x3() -> WorkshopInstance:
    return WorkshopInstance(
        name="pipeline_baseline_3x3",
        jobs=[
            Job(
                job_id=j,
                operations=[
                    Operation(job_id=j, sequence_idx=i, machine_id=(j + i) % 3, duration=3)
                    for i in range(3)
                ],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=m) for m in range(3)],
        best_known_makespan=9,
    )


def _infeasible_instance() -> WorkshopInstance:
    return WorkshopInstance(
        name="pipeline_infeasible",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=10),
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
        machine_unavailability=[
            MachineUnavailabilitySpec(machine_id=0, periods=[(0, 5), (10, 20)]),
        ],
    )


# ---------- Cas SOLVED -> ACCEPT ----------


def test_accept_on_baseline_3x3() -> None:
    report = run_pipeline(_baseline_3x3(), **CFG)
    assert report.decision.kind is PipelineDecisionKind.ACCEPT
    assert report.simulation is not None
    assert report.score is not None
    assert report.score.gate_passed
    assert report.simulation.verdict.value == "ACCEPT"
    assert report.circuit_breaker.outcome is CircuitBreakerOutcome.SOLVED


# ---------- Cas INFEASIBLE -> REJECT ----------


def test_reject_on_infeasible_instance() -> None:
    report = run_pipeline(_infeasible_instance(), **CFG)
    assert report.decision.kind is PipelineDecisionKind.REJECT
    assert report.circuit_breaker.outcome is CircuitBreakerOutcome.INFEASIBLE
    assert report.simulation is None, "Simulation skipped si non SOLVED"
    assert report.score is None
    assert any("Circuit breaker" in r for r in report.decision.reasons)


# ---------- Cas EXHAUSTED -> REJECT (monkeypatch) ----------


def test_reject_on_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_solve(_self: JSSPSolver, instance: WorkshopInstance) -> SolverResult:
        return SolverResult(
            instance_name=instance.name,
            status=SolverStatus.UNKNOWN,
            makespan=None,
            schedule=[],
            solve_time_seconds=0.05,
        )

    monkeypatch.setattr(JSSPSolver, "solve", fake_solve)
    cfg = {**CFG, "time_budgets_s": (0.5, 1.0, 2.0)}
    report = run_pipeline(_baseline_3x3(), **cfg)
    assert report.decision.kind is PipelineDecisionKind.REJECT
    assert report.circuit_breaker.outcome is CircuitBreakerOutcome.EXHAUSTED
    assert report.simulation is None
    assert report.score is None


# ---------- Cas simulation REJECT -> REJECT ----------


def test_reject_when_simulation_rejects() -> None:
    """Setup ratio 90 % -> simulation REJECT. Le pipeline doit suivre."""
    instance = WorkshopInstance(
        name="pipeline_setup_extreme",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5, family_id=0)
                ],
            ),
            Job(
                job_id=1,
                operations=[
                    Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5, family_id=1)
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
        transition_matrix=[[0, 100], [100, 0]],
    )
    report = run_pipeline(instance, **CFG)
    # Le solveur va trouver une solution (FEASIBLE/OPTIMAL avec setup 100), mais
    # la simulation va detecter setup_ratio extreme -> REJECT
    assert report.decision.kind is PipelineDecisionKind.REJECT
    assert report.circuit_breaker.outcome is CircuitBreakerOutcome.SOLVED
    assert report.simulation is not None
    assert report.simulation.verdict.value == "REJECT"
    assert any("Simulation REJECT" in r for r in report.decision.reasons)


# ---------- Cas score gate failed ----------


def test_reject_when_score_gate_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate failed = schedule incoherente. Doit donner REJECT meme si CP-SAT dit OPTIMAL."""

    def bogus_solve(_self: JSSPSolver, instance: WorkshopInstance) -> SolverResult:
        # Schedule deliberement incoherente : sequence_idx 2 inexistant
        return SolverResult(
            instance_name=instance.name,
            status=SolverStatus.OPTIMAL,
            makespan=9,
            schedule=[
                ScheduleAssignment(job_id=0, sequence_idx=99, machine_id=0, start=0, end=3),
            ],
            solve_time_seconds=0.1,
        )

    monkeypatch.setattr(JSSPSolver, "solve", bogus_solve)
    report = run_pipeline(_baseline_3x3(), **CFG)
    assert report.decision.kind is PipelineDecisionKind.REJECT
    assert report.score is not None
    assert not report.score.gate_passed
    assert any("Score gate" in r for r in report.decision.reasons)


# ---------- Pas d'erreur silenciuse : si ACCEPT, validate_schedule passe ----------


def test_accept_implies_validate_schedule_clean() -> None:
    report = run_pipeline(_baseline_3x3(), **CFG)
    assert report.decision.kind is PipelineDecisionKind.ACCEPT
    errors = validate_schedule(_baseline_3x3(), report.circuit_breaker.final_result.schedule)
    assert errors == []


# ---------- Test E2E Gate 1 : 20 ateliers meca synthetiques ----------


@pytest.mark.slow
def test_gate1_no_silent_errors_on_20_synthetic_workshops() -> None:
    """Gate 1 : aucune erreur silencieuse sur 20 ateliers generes.

    Definition d'erreur silencieuse : le pipeline retourne ACCEPT sur un
    planning que `validate_schedule` rejetterait. Si ca arrive une seule fois,
    le hard gate du scoring a un bug.
    """
    n_workshops = 20
    base_params = {
        "n_machines_min": 3,
        "n_machines_max": 5,
        "n_operators_min": 3,
        "n_operators_max": 5,
        "n_jobs_min": 3,
        "n_jobs_max": 5,
        "operations_per_job_min": 2,
        "operations_per_job_max": 4,
    }

    accepts = 0
    warns = 0
    rejects = 0
    silent_errors: list[tuple[str, list[str]]] = []
    reports: list[PipelineReport] = []

    for seed in range(n_workshops):
        params = GenerationParams(**base_params, seed=seed)
        synthetic = generate_workshop(params)
        instance = synthetic_to_jssp_instance(
            synthetic,
            name=f"gate1_w{seed}",
            enable_setup=False,  # setup-pattern bottleneck connu (Phase 1.1.opt)
        )
        report = run_pipeline(instance, **CFG)
        reports.append(report)

        if report.decision.kind is PipelineDecisionKind.ACCEPT:
            accepts += 1
            errs = validate_schedule(instance, report.circuit_breaker.final_result.schedule)
            if errs:
                silent_errors.append((instance.name, errs))
        elif report.decision.kind is PipelineDecisionKind.WARN:
            warns += 1
        else:
            rejects += 1

    assert silent_errors == [], f"Erreurs silencieuses detectees : {silent_errors}"
    assert accepts + warns + rejects == n_workshops
    # Au moins un ACCEPT attendu sur des ateliers petits (sinon le pipeline est cassé)
    assert accepts > 0, f"Aucun ACCEPT sur {n_workshops} ateliers, suspect"
