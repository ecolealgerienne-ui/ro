"""Tests du module `src.core.circuit_breaker` (engine generique).

Couvre :
- Outcome SOLVED des la 1re tentative (cas nominal)
- Outcome INFEASIBLE detecte tot (preuve par CP-SAT, pas de retry inutile)
- Outcome EXHAUSTED si toutes les tentatives retournent UNKNOWN (monkeypatch)
- mis_extractor custom invoque sur INFEASIBLE et EXHAUSTED, pas sur SOLVED
- Validation des arguments (budgets vides / negatifs)
- Garantie : nombre de tentatives <= len(time_budgets_s)
"""

from __future__ import annotations

import pytest

from src.core.circuit_breaker import (
    DEFAULT_TIME_BUDGETS_S,
    AttemptKind,
    CircuitBreakerOutcome,
    solve_with_circuit_breaker,
)
from src.core.models import Job, Machine, MachineUnavailabilitySpec, Operation, WorkshopInstance
from src.core.solver import JSSPSolver, ScheduleAssignment, SolverResult, SolverStatus


def _baseline_3x3() -> WorkshopInstance:
    """Instance OPTIMAL connue : 3 jobs x 3 machines, gammes circulaires, dur 3, opt = 9."""
    return WorkshopInstance(
        name="cb_baseline_3x3",
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
    """Instance INFEASIBLE : 1 op dur 10, fenetres dispo [5,10] et [20,25] de 5 chacune.

    horizon calcule = 10 + 5 + 10 = 25, mais aucun creneau de 10 contigus.
    """
    return WorkshopInstance(
        name="cb_infeasible_unavail",
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


# ---------- Cas nominal SOLVED ----------


def test_solved_on_first_attempt() -> None:
    instance = _baseline_3x3()
    out = solve_with_circuit_breaker(instance, time_budgets_s=(5.0,))
    assert out.outcome is CircuitBreakerOutcome.SOLVED
    assert out.n_attempts == 1
    assert out.attempts[0].kind is AttemptKind.INITIAL
    assert out.final_result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert out.mis_summary is None


def test_solved_does_not_call_mis_extractor() -> None:
    instance = _baseline_3x3()
    calls: list[str] = []

    def tracking_extractor(_instance: WorkshopInstance) -> str:
        calls.append(_instance.name)
        return "should not be called"

    out = solve_with_circuit_breaker(
        instance, time_budgets_s=(5.0,), mis_extractor=tracking_extractor
    )
    assert out.outcome is CircuitBreakerOutcome.SOLVED
    assert calls == []


# ---------- Cas INFEASIBLE ----------


def test_infeasible_detected_and_stops_early() -> None:
    """CP-SAT prouve l'infaisabilite -> on s'arrete a la 1re tentative."""
    instance = _infeasible_instance()
    out = solve_with_circuit_breaker(instance, time_budgets_s=(5.0, 10.0, 15.0))
    assert out.outcome is CircuitBreakerOutcome.INFEASIBLE
    assert out.n_attempts == 1, "Aucun retry attendu apres preuve d'infaisabilite"
    assert out.final_result.status is SolverStatus.INFEASIBLE
    assert out.mis_summary is not None
    # default_mis_extractor (Phase 1.8) produit un summary commencant par "INFEASIBLE".
    assert "INFEASIBLE" in out.mis_summary


def test_infeasible_calls_custom_mis_extractor() -> None:
    instance = _infeasible_instance()
    calls: list[str] = []

    def custom_extractor(received: WorkshopInstance) -> str:
        calls.append(received.name)
        return "INSTANCE INVIABLE: unavailability blocks the only op"

    out = solve_with_circuit_breaker(
        instance, time_budgets_s=(5.0,), mis_extractor=custom_extractor
    )
    assert out.outcome is CircuitBreakerOutcome.INFEASIBLE
    assert calls == [instance.name]
    assert out.mis_summary is not None
    assert "INVIABLE" in out.mis_summary


# ---------- Cas EXHAUSTED (monkeypatch) ----------


def _make_unknown_result(instance_name: str) -> SolverResult:
    return SolverResult(
        instance_name=instance_name,
        status=SolverStatus.UNKNOWN,
        makespan=None,
        schedule=[],
        solve_time_seconds=0.05,
    )


def test_exhausted_after_all_unknown_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tous les budgets retournent UNKNOWN -> outcome EXHAUSTED, MIS appele."""

    def fake_solve(self: JSSPSolver, instance: WorkshopInstance) -> SolverResult:
        return _make_unknown_result(instance.name)

    monkeypatch.setattr(JSSPSolver, "solve", fake_solve)

    instance = _baseline_3x3()
    out = solve_with_circuit_breaker(instance, time_budgets_s=(0.5, 1.0, 2.0))
    assert out.outcome is CircuitBreakerOutcome.EXHAUSTED
    assert out.n_attempts == 3
    assert all(a.status is SolverStatus.UNKNOWN for a in out.attempts)
    assert out.mis_summary is not None


def test_exhausted_uses_increasing_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les attempts memorisent les budgets dans l'ordre fourni."""
    monkeypatch.setattr(JSSPSolver, "solve", lambda self, inst: _make_unknown_result(inst.name))
    instance = _baseline_3x3()
    out = solve_with_circuit_breaker(instance, time_budgets_s=(1.0, 5.0, 30.0))
    assert [a.time_limit_s for a in out.attempts] == [1.0, 5.0, 30.0]
    assert out.attempts[0].kind is AttemptKind.INITIAL
    assert out.attempts[1].kind is AttemptKind.RETRY
    assert out.attempts[2].kind is AttemptKind.RETRY


# ---------- Retry apres UNKNOWN puis SOLVED ----------


def test_retry_after_unknown_then_solved(monkeypatch: pytest.MonkeyPatch) -> None:
    """Premier UNKNOWN -> retry -> 2e tentative trouve la solution."""
    call_count = {"n": 0}

    def stateful_solve(self: JSSPSolver, instance: WorkshopInstance) -> SolverResult:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _make_unknown_result(instance.name)
        return SolverResult(
            instance_name=instance.name,
            status=SolverStatus.OPTIMAL,
            makespan=9,
            schedule=[
                ScheduleAssignment(
                    job_id=j,
                    sequence_idx=i,
                    machine_id=(j + i) % 3,
                    start=((j + i) % 3) * 3,
                    end=((j + i) % 3) * 3 + 3,
                )
                for j in range(3)
                for i in range(3)
            ],
            solve_time_seconds=0.5,
        )

    monkeypatch.setattr(JSSPSolver, "solve", stateful_solve)
    instance = _baseline_3x3()
    out = solve_with_circuit_breaker(instance, time_budgets_s=(0.5, 5.0, 30.0))
    assert out.outcome is CircuitBreakerOutcome.SOLVED
    assert out.n_attempts == 2
    assert out.attempts[0].status is SolverStatus.UNKNOWN
    assert out.attempts[1].status is SolverStatus.OPTIMAL
    assert out.mis_summary is None


# ---------- Validation arguments ----------


def test_empty_budgets_raises() -> None:
    instance = _baseline_3x3()
    with pytest.raises(ValueError, match=r"vide"):
        solve_with_circuit_breaker(instance, time_budgets_s=())


def test_zero_budget_raises() -> None:
    instance = _baseline_3x3()
    with pytest.raises(ValueError, match=r"> 0"):
        solve_with_circuit_breaker(instance, time_budgets_s=(5.0, 0.0, 10.0))


def test_negative_budget_raises() -> None:
    instance = _baseline_3x3()
    with pytest.raises(ValueError, match=r"> 0"):
        solve_with_circuit_breaker(instance, time_budgets_s=(-1.0,))


def test_default_budgets_have_three_steps() -> None:
    """Le defaut doit refleter le critere de sortie : '3 retries -> bascule MIS'."""
    assert len(DEFAULT_TIME_BUDGETS_S) == 3
    assert all(b > 0 for b in DEFAULT_TIME_BUDGETS_S)
    assert list(DEFAULT_TIME_BUDGETS_S) == sorted(DEFAULT_TIME_BUDGETS_S), (
        "Budgets attendus croissants"
    )
