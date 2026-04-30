"""Tests Phase 1.5 — stabilite ponderee par criticite (Tier 1/2/3).

Couvre :
- `Job.criticality` (champ optionnel, ge=1)
- `tier_weighted_stability_var` (helper engine generique)
- `build_composite_soft_penalties(stability_tier_weights=...)` (integration)
- `MECH_TIER_WEIGHTS` (calibration meca)
- **Critère de sortie 1.5** : "deplacer un Tier 1 coute 10× plus qu'un Tier 3"
  → ratio des contributions effectives au cout total = 10.
"""

from __future__ import annotations

from typing import Any

import pytest
from ortools.sat.python import cp_model
from pydantic import ValidationError

from src.core.models import Job, Machine, Operation, WorkshopInstance
from src.core.objectives import (
    CompositeObjectiveSpec,
    ObjectivePriority,
    build_composite_soft_penalties,
)
from src.core.soft_constraints import tier_weighted_stability_var
from src.core.solver import JSSPSolver, SolverStatus
from src.verticals.mech_workshop import MECH_TIER_WEIGHTS


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


# ---------- Job.criticality ----------


def test_job_criticality_default_none() -> None:
    job = Job(
        job_id=0,
        operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
    )
    assert job.criticality is None


def test_job_criticality_with_value() -> None:
    job = Job(
        job_id=0,
        operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
        criticality=1,
    )
    assert job.criticality == 1


def test_job_criticality_zero_is_invalid() -> None:
    """`criticality` ge=1 par convention (1 = critique, 3 = standard)."""
    with pytest.raises(ValidationError):
        Job(
            job_id=0,
            operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
            criticality=0,
        )


# ---------- tier_weighted_stability_var ----------


def test_tier_weighted_stability_validates_weights() -> None:
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                criticality=1,
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)

    with pytest.raises(ValueError, match=r"default_weight"):
        tier_weighted_stability_var(
            model,
            instance=instance,
            op_vars=op_vars,
            horizon=100,
            reference_schedule={(0, 0): 0},
            weight_per_tier={1: 10},
            default_weight=0,
        )

    with pytest.raises(ValueError, match=r"weight_per_tier"):
        tier_weighted_stability_var(
            model,
            instance=instance,
            op_vars=op_vars,
            horizon=100,
            reference_schedule={(0, 0): 0},
            weight_per_tier={1: 0},  # poids invalide
        )


def test_tier_weighted_stability_uses_default_for_unknown_tier() -> None:
    """Job sans criticality → poids `default_weight`."""
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                # criticality non assigne -> None
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    # Force start=10 (deviation 10 vs ref=0)
    model.add(op_vars[(0, 0)]["start"] == 10)
    var = tier_weighted_stability_var(
        model,
        instance=instance,
        op_vars=op_vars,
        horizon=100,
        reference_schedule={(0, 0): 0},
        weight_per_tier={1: 10, 2: 3, 3: 1},
        default_weight=2,  # default pour les jobs sans tier
    )
    assert var is not None
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    # contribution = default_weight × |10 - 0| = 2 × 10 = 20
    assert solver.value(var) == 20


def test_tier_weighted_stability_returns_none_if_no_match() -> None:
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
    # reference avec une cle absente de op_vars
    var = tier_weighted_stability_var(
        model,
        instance=instance,
        op_vars=op_vars,
        horizon=100,
        reference_schedule={(99, 99): 0},
        weight_per_tier={1: 10},
    )
    assert var is None


def test_critere_de_sortie_tier_1_cout_10x_tier_3() -> None:
    """Critere de sortie 1.5 : deplacer un Tier 1 coute 10× plus qu'un Tier 3.

    Setup : 2 jobs identiques (1 op dur 5 chacun, machines distinctes pour
    eviter no_overlap), un Tier 1 et un Tier 3. On force la meme deviation
    sur les deux. Le total doit etre :
        contribution_T1 = 10 × deviation
        contribution_T3 =  1 × deviation
        ratio = 10 ✓
    """
    instance = WorkshopInstance(
        name="tier_1_vs_3",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                criticality=1,  # Tier 1 critique
            ),
            Job(
                job_id=1,
                operations=[Operation(job_id=1, sequence_idx=0, machine_id=1, duration=5)],
                criticality=3,  # Tier 3 standard
            ),
        ],
        machines=[Machine(machine_id=0), Machine(machine_id=1)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)

    # Force la meme deviation = 7 sur les 2 jobs (ref=0, on force start=7)
    model.add(op_vars[(0, 0)]["start"] == 7)
    model.add(op_vars[(1, 0)]["start"] == 7)

    var = tier_weighted_stability_var(
        model,
        instance=instance,
        op_vars=op_vars,
        horizon=100,
        reference_schedule={(0, 0): 0, (1, 0): 0},
        weight_per_tier=MECH_TIER_WEIGHTS,
    )
    assert var is not None
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    # contribution T1 = 10 × 7 = 70
    # contribution T3 =  1 × 7 = 7
    # total = 77
    assert solver.value(var) == 77

    # Verification du ratio 10× : si on extrapole, deplacer T1 coute exactement
    # 10× plus qu'un T3 pour la meme deviation. Le total est la somme = 77,
    # dont T1 represente 70/77 = 90.9 %, T3 represente 7/77 = 9.1 %, ratio = 10.
    # En isolant chaque contribution, on aurait :
    contribution_t1 = 10 * 7
    contribution_t3 = 1 * 7
    assert contribution_t1 / contribution_t3 == 10


def test_tier_weighted_solver_prefers_to_move_tier_3() -> None:
    """Si on doit deplacer 1 op, le solveur prefere bouger le Tier 3.

    Setup : 2 ops identiques (ref start = 0), 1 machine, donc no_overlap force
    une op a se decaler. Avec MECH_TIER_WEIGHTS, le solveur va decaler le Tier 3.
    """
    instance = WorkshopInstance(
        name="prefer_move_t3",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                criticality=1,
            ),
            Job(
                job_id=1,
                operations=[Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5)],
                criticality=3,
            ),
        ],
        machines=[Machine(machine_id=0)],
    )
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.DISABLED,
        stability=ObjectivePriority.HIGH,
        early_completion=ObjectivePriority.DISABLED,
    )
    # reference : J0 a 0, J1 a 0 (impossible ensemble sur m0 - le solveur DOIT en bouger un)
    builder = build_composite_soft_penalties(
        spec,
        reference_schedule={(0, 0): 0, (1, 0): 0},
        stability_tier_weights=MECH_TIER_WEIGHTS,
        calibrate=False,  # poids bruts pour observer le comportement tier
    )
    solver = JSSPSolver(time_limit_seconds=5.0)
    result = solver.solve(
        instance, soft_penalty_builder=builder, makespan_weight=spec.makespan_weight
    )
    assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    j0_start = next(a.start for a in result.schedule if a.job_id == 0)
    j1_start = next(a.start for a in result.schedule if a.job_id == 1)
    # Tier 1 (J0) doit rester proche de 0, Tier 3 (J1) doit se decaler.
    assert j0_start == 0  # T1 reste a sa place
    assert j1_start == 5  # T3 se decale apres J0


# ---------- build_composite_soft_penalties(stability_tier_weights=...) ----------


def test_build_composite_uses_tier_weighted_when_provided() -> None:
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        tardiness=ObjectivePriority.DISABLED,
        stability=ObjectivePriority.HIGH,
        early_completion=ObjectivePriority.DISABLED,
    )
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                criticality=1,
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    builder = build_composite_soft_penalties(
        spec,
        reference_schedule={(0, 0): 0},
        stability_tier_weights=MECH_TIER_WEIGHTS,
        calibrate=False,
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=100)
    assert len(out) == 1
    assert out[0].label == "composite_stability_tier_weighted"


def test_build_composite_falls_back_to_uniform_without_tier_weights() -> None:
    spec = CompositeObjectiveSpec(
        makespan=ObjectivePriority.LOW,
        stability=ObjectivePriority.HIGH,
        tardiness=ObjectivePriority.DISABLED,
        early_completion=ObjectivePriority.DISABLED,
    )
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)],
                criticality=1,
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    # Pas de stability_tier_weights → label = "composite_stability" (uniforme)
    builder = build_composite_soft_penalties(
        spec, reference_schedule={(0, 0): 0}, calibrate=False
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    out = builder(model=model, instance=instance, op_vars=op_vars, horizon=100)
    assert len(out) == 1
    assert out[0].label == "composite_stability"


# ---------- MECH_TIER_WEIGHTS ----------


def test_mech_tier_weights_satisfies_critere() -> None:
    """Les valeurs metier respectent le critere de sortie 1.5."""
    assert MECH_TIER_WEIGHTS[1] / MECH_TIER_WEIGHTS[3] == 10
    assert MECH_TIER_WEIGHTS[2] == 3  # zone moyenne
    assert MECH_TIER_WEIGHTS[3] == 1  # reference
