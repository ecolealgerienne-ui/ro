"""Tests Phase 1.3 — calibration dynamique des poids.

Couvre :
- `SoftPenaltyVar.expected_max` — annotation optionnelle backward-compatible
- `calibrate_penalty_weights()` — formule, edge cases (None, target invalide)
- `build_composite_soft_penalties(calibrate=True)` — toggle de calibration
- Cohabitation calibration ON / OFF
- **Critère de sortie 1.3** : sur un cas multi-objectifs avec des échelles très
  différentes, la calibration empêche un objectif d'écraser les autres.
"""

from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from src.core.models import Job, Machine, Operation, WorkshopInstance
from src.core.objectives import (
    CALIBRATION_TARGET,
    PRIORITY_TO_WEIGHT,
    CompositeObjectiveSpec,
    ObjectivePriority,
    build_composite_soft_penalties,
    calibrate_penalty_weights,
)
from src.core.soft_constraints import SoftPenaltyVar
from src.core.solver import JSSPSolver, SolverStatus

# ---------- SoftPenaltyVar.expected_max (rétro-compat) ----------


def test_soft_penalty_var_expected_max_default_none() -> None:
    model = cp_model.CpModel()
    v = model.new_int_var(0, 10, "v")
    sp = SoftPenaltyVar(label="x", weight=1, var=v)
    assert sp.expected_max is None


def test_soft_penalty_var_with_expected_max() -> None:
    model = cp_model.CpModel()
    v = model.new_int_var(0, 10, "v")
    sp = SoftPenaltyVar(label="x", weight=1, var=v, expected_max=100)
    assert sp.expected_max == 100


# ---------- calibrate_penalty_weights ----------


def test_calibrate_leaves_unchanged_when_no_expected_max() -> None:
    model = cp_model.CpModel()
    v = model.new_int_var(0, 10, "v")
    sp = SoftPenaltyVar(label="x", weight=42, var=v)  # pas d'expected_max
    out = calibrate_penalty_weights([sp])
    assert len(out) == 1
    assert out[0].weight == 42
    assert out[0].label == "x"


def test_calibrate_rescales_to_target() -> None:
    """weight 1 + expected_max 100 + target 1000 → new_weight = round(1*1000/100) = 10."""
    model = cp_model.CpModel()
    v = model.new_int_var(0, 100, "v")
    sp = SoftPenaltyVar(label="x", weight=1, var=v, expected_max=100)
    out = calibrate_penalty_weights([sp], target=1000)
    assert out[0].weight == 10


def test_calibrate_handles_priority_amplification() -> None:
    """weight 25 (priorité HIGH) + expected_max 100 + target 1000 → 250."""
    model = cp_model.CpModel()
    v = model.new_int_var(0, 100, "v")
    sp = SoftPenaltyVar(
        label="x",
        weight=PRIORITY_TO_WEIGHT[ObjectivePriority.HIGH],
        var=v,
        expected_max=100,
    )
    out = calibrate_penalty_weights([sp], target=1000)
    # 25 * 1000 / 100 = 250
    assert out[0].weight == 250


def test_calibrate_floor_at_1() -> None:
    """expected_max très grand → poids final ne descend pas sous 1."""
    model = cp_model.CpModel()
    v = model.new_int_var(0, 10, "v")
    sp = SoftPenaltyVar(label="x", weight=1, var=v, expected_max=100_000)
    out = calibrate_penalty_weights([sp], target=1000)
    # 1 * 1000 / 100000 = 0.01 → max(1, 0) = 1
    assert out[0].weight == 1


def test_calibrate_preserves_expected_max_for_traceability() -> None:
    """L'expected_max reste annoté apres calibration (pour debugging post-solving)."""
    model = cp_model.CpModel()
    v = model.new_int_var(0, 10, "v")
    sp = SoftPenaltyVar(label="x", weight=10, var=v, expected_max=100)
    out = calibrate_penalty_weights([sp])
    assert out[0].expected_max == 100


def test_calibrate_skip_negative_or_zero_expected_max() -> None:
    """expected_max <= 0 est une erreur silencieusement ignoree (pas de division)."""
    model = cp_model.CpModel()
    v = model.new_int_var(0, 10, "v")
    sp_neg = SoftPenaltyVar(label="x", weight=10, var=v, expected_max=-5)
    sp_zero = SoftPenaltyVar(label="y", weight=10, var=v, expected_max=0)
    out = calibrate_penalty_weights([sp_neg, sp_zero])
    assert all(sp.weight == 10 for sp in out)


def test_calibrate_invalid_target_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match=r"target"):
        calibrate_penalty_weights([], target=0)


def test_calibrate_does_not_mutate_input() -> None:
    model = cp_model.CpModel()
    v = model.new_int_var(0, 10, "v")
    sp = SoftPenaltyVar(label="x", weight=1, var=v, expected_max=100)
    inputs = [sp]
    out = calibrate_penalty_weights(inputs, target=1000)
    assert sp.weight == 1  # input non mute
    assert out[0].weight == 10
    assert inputs[0] is sp


# ---------- build_composite_soft_penalties(calibrate=...) ----------


def _instance_with_deadline() -> WorkshopInstance:
    return WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                deadline=3,
            ),
            Job(
                job_id=1,
                operations=[Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5)],
                deadline=3,
            ),
        ],
        machines=[Machine(machine_id=0)],
    )


def _build_op_vars(
    model: Any, instance: WorkshopInstance, horizon: int
) -> dict[tuple[int, int], dict[str, Any]]:
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


def test_composite_calibrate_true_modifies_weights() -> None:
    """Avec calibrate=True, les poids des objectifs universels sont rescaled."""
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.HIGH,
        stability=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.DISABLED,
    )
    instance = _instance_with_deadline()
    horizon = 100
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon)
    builder = build_composite_soft_penalties(spec, calibrate=True)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=horizon)
    assert len(out) == 1
    sp = out[0]
    # tardiness expected_max = horizon * n_jobs_with_deadline = 100 * 2 = 200
    # weight raw = HIGH = 25 ; calibre = max(1, 25 * 1000 / 200) = 125
    assert sp.expected_max == 200
    assert sp.weight == 125


def test_composite_calibrate_false_keeps_raw_weights() -> None:
    """Avec calibrate=False, comportement Phase 1.2 (poids = priorité brute)."""
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.HIGH,
        stability=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.DISABLED,
    )
    instance = _instance_with_deadline()
    horizon = 100
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon)
    builder = build_composite_soft_penalties(spec, calibrate=False)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=horizon)
    sp = out[0]
    assert sp.weight == PRIORITY_TO_WEIGHT[ObjectivePriority.HIGH]  # 25, brut


# ---------- Critère de sortie 1.3 : pas d'écrasement multi-échelle ----------


def test_calibration_prevents_dominance_of_large_scale_penalty() -> None:
    """Critère de sortie 1.3.

    Cas pédagogique : 2 penalites de même priorité MAIS d'échelles très différentes
    (tardiness en ~horizon × n_jobs vs avoid_period en count d'ops).

    Sans calibration : tardiness écrase avoid_period (poids brut identique mais
    valeur 100x plus grande).

    Avec calibration : les deux contribuent dans le meme ordre de grandeur, le
    solveur respecte les deux objectifs.
    """
    instance = WorkshopInstance(
        name="multi_scale",
        jobs=[
            Job(
                job_id=j,
                operations=[Operation(job_id=j, sequence_idx=0, machine_id=0, duration=3)],
                deadline=5,  # toutes serrees
            )
            for j in range(4)
        ],
        machines=[Machine(machine_id=0)],
    )

    # Penalty A : tardiness aggregate (échelle ~ horizon × n_jobs = 100 × 4 = 400)
    # Penalty B : un compteur fictif (échelle ~ 4)
    # Si on les met tous deux à priorité MEDIUM (5), sans calibration la
    # tardiness domine d'un facteur 100. Avec calibration, les deux sont dans
    # le même ordre de grandeur.

    def _fake_low_scale_extras(*, model, instance, op_vars, horizon):
        """Une penalite fictive de tres petite echelle (count <= 4)."""
        flag_sum = model.new_int_var(0, 4, "fake_low")
        # On somme des bool fictifs : tous a 0 dans la solution optimale.
        flags = [model.new_bool_var(f"fk_{i}") for i in range(4)]
        model.add(flag_sum == sum(flags))
        return [
            SoftPenaltyVar(
                label="fake_low_scale",
                weight=PRIORITY_TO_WEIGHT[ObjectivePriority.MEDIUM],  # 5
                var=flag_sum,
                expected_max=4,
            )
        ]

    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.MEDIUM,
        stability=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.DISABLED,
    )

    # Avec calibration ON : on inspecte les poids effectifs
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    builder_calib = build_composite_soft_penalties(
        spec, vertical_extras=_fake_low_scale_extras, calibrate=True
    )
    out_calib = builder_calib(model=model, instance=instance, op_vars=op_vars, horizon=100)

    by_label_calib = {sp.label: sp for sp in out_calib}
    tardy = by_label_calib["composite_tardiness"]
    fake = by_label_calib["fake_low_scale"]

    # Avec calibration : poids effectifs sont normalisés à ~target
    # tardiness : 5 * 1000 / 400 = 12.5 → 12 ou 13 (round)
    # fake :     5 * 1000 / 4   = 1250
    # Ratio fake/tardy avec calibration ≈ 100 (fake amplifié pour compenser sa petite echelle)
    assert tardy.weight in (12, 13)
    assert fake.weight == 1250

    # Sans calibration : ratio = 1 (mais valeur de tardy ~ 100x plus grande)
    model2 = cp_model.CpModel()
    op_vars2 = _build_op_vars(model2, instance, horizon=100)
    builder_raw = build_composite_soft_penalties(
        spec, vertical_extras=_fake_low_scale_extras, calibrate=False
    )
    out_raw = builder_raw(model=model2, instance=instance, op_vars=op_vars2, horizon=100)
    by_label_raw = {sp.label: sp for sp in out_raw}
    assert by_label_raw["composite_tardiness"].weight == 5
    assert by_label_raw["fake_low_scale"].weight == 5
    # → sans calibration, les deux ont meme poids brut, mais tardiness ~ 100x plus grand
    #   en valeur → ecrase fake_low_scale.


def test_calibration_default_is_on() -> None:
    """Defaut de `build_composite_soft_penalties` : calibrate=True (Phase 1.3)."""
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.HIGH,
        stability=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.DISABLED,
    )
    instance = _instance_with_deadline()
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    builder = build_composite_soft_penalties(spec)  # calibrate=True par defaut
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=100)
    sp = out[0]
    # Si calibrate etait False, weight serait 25 (HIGH brut)
    assert sp.weight != 25
    assert sp.weight == 125  # 25 * 1000 / 200


def test_calibration_target_constant_value() -> None:
    """CALIBRATION_TARGET est public et vaut 1000 (sert de reference dans la doctrine)."""
    assert CALIBRATION_TARGET == 1000


# ---------- Integration solver : calibration ne casse pas le replanif ----------


def test_solver_with_calibration_preserves_replanification_behavior() -> None:
    """Test repris de 1.2 : stability CRITICAL fait retomber sur reference, meme avec calibration."""
    instance = WorkshopInstance(
        name="replan_calib",
        jobs=[
            Job(
                job_id=j,
                operations=[Operation(job_id=j, sequence_idx=0, machine_id=0, duration=3)],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=0)],
    )
    reference = {(0, 0): 0, (1, 0): 3, (2, 0): 6}
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.DISABLED,
        stability=ObjectivePriority.CRITICAL,
        early_completion=ObjectivePriority.DISABLED,
    )
    builder = build_composite_soft_penalties(spec, reference_schedule=reference, calibrate=True)
    solver = JSSPSolver(time_limit_seconds=5.0)
    result = solver.solve(
        instance, soft_penalty_builder=builder, makespan_weight=spec.makespan_weight
    )
    assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    by_job = {a.job_id: a.start for a in result.schedule}
    assert by_job[0] == 0
    assert by_job[1] == 3
    assert by_job[2] == 6
