"""Tests Phase 1.2 — objectif composite via priorites nommees.

Couvre :
- Engine helpers : `aggregate_tardiness_var`, `aggregate_completion_var`,
  `schedule_stability_var`.
- `CompositeObjectiveSpec` Pydantic + `PRIORITY_TO_WEIGHT` mapping.
- `build_composite_soft_penalties()` : produit le bon SoftPenaltyBuilder selon
  les priorites, gere DISABLED, fusionne avec `vertical_extras`.
- Integration solver avec `makespan_weight` parametrable.
- Replanification : verifie que `stability` rapproche le nouveau planning du
  reference quand priorite == HIGH.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ortools.sat.python import cp_model

from src.core.models import Job, Machine, Operation, WorkshopInstance
from src.core.objectives import (
    PRIORITY_TO_WEIGHT,
    CompositeObjectiveSpec,
    ObjectivePriority,
    build_composite_soft_penalties,
)
from src.core.soft_constraints import (
    SoftPenaltyVar,
    aggregate_completion_var,
    aggregate_tardiness_var,
    schedule_stability_var,
)
from src.core.solver import JSSPSolver, SolverStatus


def _build_op_vars(
    model: Any, instance: WorkshopInstance, horizon: int
) -> dict[tuple[int, int], dict[str, Any]]:
    """Helper : cree variables CP-SAT + no_overlap par machine."""
    op_vars: dict[tuple[int, int], dict[str, Any]] = {}
    intervals_per_machine: dict[int, list[Any]] = {m.machine_id: [] for m in instance.machines}
    for job in instance.jobs:
        for op in job.operations:
            start = model.new_int_var(0, horizon, f"s_{job.job_id}_{op.sequence_idx}")
            end = model.new_int_var(0, horizon, f"e_{job.job_id}_{op.sequence_idx}")
            interval = model.new_interval_var(
                start, op.duration, end, f"i_{job.job_id}_{op.sequence_idx}"
            )
            op_vars[(job.job_id, op.sequence_idx)] = {
                "start": start,
                "end": end,
                "interval": interval,
                "machine_id": op.machine_id,
            }
            intervals_per_machine[op.machine_id].append(interval)
    for intervals in intervals_per_machine.values():
        if len(intervals) > 1:
            model.add_no_overlap(intervals)
    return op_vars


# ---------- Engine helpers ----------


def test_aggregate_tardiness_returns_none_without_deadlines() -> None:
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    var = aggregate_tardiness_var(model, instance=instance, op_vars=op_vars, horizon=100)
    assert var is None


def test_aggregate_tardiness_sums_lateness() -> None:
    instance = WorkshopInstance(
        name="tardy",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                deadline=3,  # job dur 5 -> tardive de 2 si finit a 5
            ),
            Job(
                job_id=1,
                operations=[Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5)],
                deadline=100,  # large -> 0 tardiness
            ),
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    var = aggregate_tardiness_var(model, instance=instance, op_vars=op_vars, horizon=100)
    assert var is not None
    model.minimize(var)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    # J0 doit finir <=3 si possible : pas possible (dur 5 > deadline 3) → tardy = 2
    # J1 finit a 10 (apres J0 sur m0), tardy = max(0, 10-100) = 0
    # total = 2
    assert solver.value(var) == 2


def test_aggregate_completion_returns_none_for_empty_instance() -> None:
    """Aucun job → None (rien à sommer)."""

    # On ne peut pas creer une instance vide via Pydantic car la validation
    # exige au moins quelque chose. On simule via un stub leger.
    class _StubInst:
        def __init__(self) -> None:
            self.jobs: list = []

    model = cp_model.CpModel()
    var = aggregate_completion_var(model, instance=_StubInst(), op_vars={}, horizon=10)
    assert var is None


def test_aggregate_completion_sums_last_ends() -> None:
    instance = WorkshopInstance(
        name="comp",
        jobs=[
            Job(
                job_id=j,
                operations=[Operation(job_id=j, sequence_idx=0, machine_id=0, duration=5)],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    var = aggregate_completion_var(model, instance=instance, op_vars=op_vars, horizon=100)
    assert var is not None
    model.minimize(var)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    # 3 ops dur 5 sur 1 machine → ends 5, 10, 15 → somme = 30
    assert solver.value(var) == 30


def test_schedule_stability_zero_when_matches_reference() -> None:
    instance = WorkshopInstance(
        name="stab",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    # Reference : J0 starts at 10 ; on force le nouveau aussi a 10 -> deviation 0
    model.add(op_vars[(0, 0)]["start"] == 10)
    var = schedule_stability_var(
        model, op_vars=op_vars, horizon=100, reference_schedule={(0, 0): 10}
    )
    assert var is not None
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(var) == 0


def test_schedule_stability_returns_none_for_empty_reference() -> None:
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    var = schedule_stability_var(model, op_vars=op_vars, horizon=100, reference_schedule={})
    assert var is None


# ---------- CompositeObjectiveSpec ----------


def test_priority_to_weight_geometric_progression() -> None:
    """L'echelle 1/5/25/125 garantit qu'un cran domine clairement le precedent."""
    assert PRIORITY_TO_WEIGHT[ObjectivePriority.DISABLED] == 0
    assert PRIORITY_TO_WEIGHT[ObjectivePriority.LOW] == 1
    assert PRIORITY_TO_WEIGHT[ObjectivePriority.MEDIUM] == 5
    assert PRIORITY_TO_WEIGHT[ObjectivePriority.HIGH] == 25
    assert PRIORITY_TO_WEIGHT[ObjectivePriority.CRITICAL] == 125


def test_composite_spec_defaults() -> None:
    spec = CompositeObjectiveSpec()
    assert spec.makespan is ObjectivePriority.HIGH
    assert spec.tardiness is ObjectivePriority.MEDIUM
    assert spec.stability is ObjectivePriority.DISABLED
    assert spec.early_completion is ObjectivePriority.DISABLED


def test_composite_spec_makespan_weight_floor_at_1() -> None:
    """Si DISABLED sur makespan, le weight reste 1 (le makespan reste presente)."""
    spec = CompositeObjectiveSpec(makespan=ObjectivePriority.DISABLED)
    assert spec.makespan_weight == 1
    spec_critical = CompositeObjectiveSpec(makespan=ObjectivePriority.CRITICAL)
    assert spec_critical.makespan_weight == 125


def test_composite_spec_extra_forbidden() -> None:
    """`extra="forbid"` : champ inconnu refuse."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CompositeObjectiveSpec(unknown_field="x")  # type: ignore[call-arg]


# ---------- build_composite_soft_penalties ----------


def test_build_composite_returns_empty_when_all_disabled_no_data() -> None:
    """Tous DISABLED + pas de reference → builder retourne []."""
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.DISABLED,
        stability=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.DISABLED,
    )
    builder = build_composite_soft_penalties(spec)
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=100)
    assert out == []


def test_build_composite_with_tardiness_and_completion() -> None:
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.HIGH,
        stability=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.MEDIUM,
    )
    builder = build_composite_soft_penalties(spec)
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                deadline=3,
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=100)
    assert len(out) == 2
    labels = {sp.label for sp in out}
    assert "composite_tardiness" in labels
    assert "composite_early_completion" in labels
    # Verifier les poids derives des priorites
    sp_tardy = next(sp for sp in out if sp.label == "composite_tardiness")
    assert sp_tardy.weight == PRIORITY_TO_WEIGHT[ObjectivePriority.HIGH]  # 25
    sp_comp = next(sp for sp in out if sp.label == "composite_early_completion")
    assert sp_comp.weight == PRIORITY_TO_WEIGHT[ObjectivePriority.MEDIUM]  # 5


def test_build_composite_with_stability_and_reference() -> None:
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.DISABLED,
        stability=ObjectivePriority.HIGH,
        early_completion=ObjectivePriority.DISABLED,
    )
    builder = build_composite_soft_penalties(spec, reference_schedule={(0, 0): 10})
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=100)
    assert len(out) == 1
    assert out[0].label == "composite_stability"
    assert out[0].weight == PRIORITY_TO_WEIGHT[ObjectivePriority.HIGH]


def test_build_composite_skips_stability_without_reference() -> None:
    """Stability HIGH mais reference_schedule=None → stability skipped silencieusement."""
    spec = CompositeObjectiveSpec(stability=ObjectivePriority.HIGH)
    builder = build_composite_soft_penalties(spec)  # pas de reference
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=100)
    # Pas de stability faute de reference. Tardiness aussi DISABLED par defaut + pas de deadline.
    assert all(sp.label != "composite_stability" for sp in out)


def test_build_composite_merges_vertical_extras() -> None:
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.HIGH,
        tardiness=ObjectivePriority.DISABLED,
        stability=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.DISABLED,
    )

    def fake_extras(*, model, instance, op_vars, horizon) -> Sequence[SoftPenaltyVar]:
        # Cree un IntVar fixe pour traceabilite
        v = model.new_int_var(0, 10, "extra_v")
        model.add(v == 7)
        return [SoftPenaltyVar(label="vertical_extra", weight=42, var=v)]

    builder = build_composite_soft_penalties(spec, vertical_extras=fake_extras)
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=100)
    assert len(out) == 1
    assert out[0].label == "vertical_extra"
    assert out[0].weight == 42


# ---------- Integration solver : makespan_weight + composite ----------


def test_solver_accepts_makespan_weight() -> None:
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    solver = JSSPSolver(time_limit_seconds=5.0)
    result = solver.solve(instance, makespan_weight=25)
    assert result.status is SolverStatus.OPTIMAL
    assert result.makespan == 5
    # WeightedObjectivePattern doit etre utilise des que makespan_weight != 1
    assert "weighted_objective" in result.patterns_applied


def test_solver_composite_tardiness_changes_priority_order() -> None:
    """Avec tardiness HIGH, le job avec deadline serree finit en premier."""
    instance = WorkshopInstance(
        name="composite",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                deadline=100,  # large
            ),
            Job(
                job_id=1,
                operations=[Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5)],
                deadline=5,  # serre
            ),
        ],
        machines=[Machine(machine_id=0)],
    )
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.CRITICAL,
        stability=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.DISABLED,
    )
    builder = build_composite_soft_penalties(spec)
    solver = JSSPSolver(time_limit_seconds=5.0)
    result = solver.solve(
        instance,
        soft_penalty_builder=builder,
        makespan_weight=spec.makespan_weight,
    )
    assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    # J1 (deadline=5) doit finir <= 5
    j1_end = next(a.end for a in result.schedule if a.job_id == 1)
    assert j1_end <= 5


def test_solver_replanification_with_stability() -> None:
    """Stability HIGH + reference → nouveau planning proche du reference."""
    instance = WorkshopInstance(
        name="replan",
        jobs=[
            Job(
                job_id=j,
                operations=[Operation(job_id=j, sequence_idx=0, machine_id=0, duration=3)],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=0)],
    )
    # Reference : J0 [0,3], J1 [3,6], J2 [6,9]. On veut que le re-solve garde cet ordre.
    reference = {(0, 0): 0, (1, 0): 3, (2, 0): 6}

    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,  # makespan secondaire
        tardiness=ObjectivePriority.DISABLED,
        stability=ObjectivePriority.CRITICAL,
        early_completion=ObjectivePriority.DISABLED,
    )
    builder = build_composite_soft_penalties(spec, reference_schedule=reference)
    solver = JSSPSolver(time_limit_seconds=5.0)
    result = solver.solve(
        instance,
        soft_penalty_builder=builder,
        makespan_weight=spec.makespan_weight,
    )
    assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    # Avec stability CRITICAL, le re-solve doit retomber sur le reference exact
    # (deviation 0 minimise totalement la penalite stability)
    by_job = {a.job_id: a.start for a in result.schedule}
    assert by_job[0] == 0
    assert by_job[1] == 3
    assert by_job[2] == 6
