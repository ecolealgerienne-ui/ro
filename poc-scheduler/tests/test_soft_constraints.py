"""Tests Phase 1.6 — soft constraints integrees a l'objectif CP-SAT.

Couvre :
- Engine generique : `WeightedObjectivePattern` (combinaison makespan + penalites)
- 3 translators meca : tardiness, avoid_machine_during_period, encourage_early
- Integration solver : passage de soft_penalty_builder
- Cohabitation 5 hard + 3 soft (NoOverlap + Precedence + Setup + Calendar +
  Operator + 3 soft simultanement)
- Verification que les soft changent effectivement la schedule
"""

from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from src.core.models import (
    Job,
    Machine,
    MachineUnavailabilitySpec,
    Operation,
    SharedResourceSpec,
    WorkshopInstance,
)
from src.core.soft_constraints import SoftPenaltyVar, WeightedObjectivePattern
from src.core.solver import JSSPSolver, SolverStatus
from src.verticals.mech_workshop.agents import SoftConstraint
from src.verticals.mech_workshop.soft_translators import (
    WEIGHT_SCALE,
    translate_avoid_machine_during_period,
    translate_encourage_early_completion,
    translate_limit_ops_per_day_on_machine,
    translate_prefer_grouping_by_client,
    translate_prefer_grouping_by_family,
    translate_soft_constraints,
    translate_tardiness_per_job,
)

# ---------- Engine : WeightedObjectivePattern ----------


def test_weighted_objective_no_soft_equals_makespan_only() -> None:
    """Sans soft penalties, le pattern est equivalent au MakespanObjectivePattern."""
    model = cp_model.CpModel()
    end1 = model.new_int_var(0, 100, "e1")
    end2 = model.new_int_var(0, 100, "e2")
    model.add(end1 == 30)
    model.add(end2 == 50)
    makespan_var = WeightedObjectivePattern().apply(model, end_vars=[end1, end2], horizon=100)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(makespan_var) == 50


def test_weighted_objective_soft_changes_solution() -> None:
    """Avec une penalite proportionnelle au makespan, l'objectif change la valeur."""
    model = cp_model.CpModel()
    end_var = model.new_int_var(10, 100, "end")
    # Sans penalite, le solveur prendrait n'importe quelle valeur >= 10
    # avec makespan minimisation strict. Avec une penalite "encourage end>=10",
    # le minimum est end=10 (sum makespan + 1*end → 20, vs 100+100=200).
    penalty_var = end_var  # penalite = end_var directement
    sp = SoftPenaltyVar(label="encourage_low_end", weight=1, var=penalty_var)
    makespan_var = WeightedObjectivePattern().apply(
        model, end_vars=[end_var], horizon=100, soft_penalties=[sp]
    )
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(makespan_var) == 10
    # solver.objective_value = 1*10 + 1*10 = 20 (somme ponderee, pas le makespan)
    assert int(solver.objective_value) == 20


def test_weighted_objective_validates_inputs() -> None:
    model = cp_model.CpModel()
    end = model.new_int_var(0, 10, "e")
    pattern = WeightedObjectivePattern()
    try:
        pattern.apply(model, end_vars=[], horizon=10)
        raise AssertionError("ValueError attendu pour end_vars vide")
    except ValueError as e:
        assert "end_vars" in str(e)
    try:
        pattern.apply(model, end_vars=[end], horizon=-1)
        raise AssertionError("ValueError attendu pour horizon < 0")
    except ValueError as e:
        assert "horizon" in str(e)
    bad_sp = SoftPenaltyVar(label="bad", weight=0, var=end)
    try:
        pattern.apply(model, end_vars=[end], horizon=10, soft_penalties=[bad_sp])
        raise AssertionError("ValueError attendu pour weight < 1")
    except ValueError as e:
        assert "weight" in str(e)


# ---------- Helpers tests translators ----------


def _instance_two_jobs_with_deadlines(
    deadlines: tuple[int | None, int | None],
    clients: tuple[str | None, str | None] = (None, None),
) -> WorkshopInstance:
    return WorkshopInstance(
        name="two_jobs_deadlines",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5),
                ],
                deadline=deadlines[0],
                client=clients[0],
            ),
            Job(
                job_id=1,
                operations=[
                    Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5),
                ],
                deadline=deadlines[1],
                client=clients[1],
            ),
        ],
        machines=[Machine(machine_id=0)],
    )


def _build_op_vars(
    model: Any, instance: WorkshopInstance, horizon: int
) -> dict[tuple[int, int], dict[str, Any]]:
    """Cree les variables CP-SAT pour les ops + ajoute le no_overlap par machine."""
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


# ---------- Translator : tardiness_per_job ----------


def test_tardiness_translator_returns_none_if_no_deadline() -> None:
    instance = _instance_two_jobs_with_deadlines((None, None))
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="x",
        category="client_priority",
        parameters={"client_reference": "Safran"},
        weight_hint=0.7,
        weight_rationale="x",
        confidence="high",
    )
    sp = translate_tardiness_per_job(
        model, instance=instance, op_vars=op_vars, horizon=100, constraint=sc
    )
    assert sp is None


def test_tardiness_translator_filters_by_client() -> None:
    instance = _instance_two_jobs_with_deadlines(deadlines=(3, 100), clients=("Safran", "Bosch"))
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="OF Safran avant deadline",
        category="client_priority",
        parameters={"client_reference": "Safran"},
        weight_hint=0.7,
        weight_rationale="x",
        confidence="high",
    )
    sp = translate_tardiness_per_job(
        model, instance=instance, op_vars=op_vars, horizon=100, constraint=sc
    )
    assert sp is not None
    assert "Safran" in sp.label
    assert sp.weight == int(0.7 * WEIGHT_SCALE)


# ---------- Translator : avoid_machine_during_period ----------


def test_avoid_machine_during_period_zero_overlap_when_op_outside() -> None:
    """Si l'op se range hors de [period_start, period_end], pas de penalite."""
    instance = _instance_two_jobs_with_deadlines((None, None))
    model = cp_model.CpModel()
    horizon = 100
    op_vars = _build_op_vars(model, instance, horizon)
    # On force start=20, end=25 et start=30, end=35 (hors de [50, 80])
    model.add(op_vars[(0, 0)]["start"] == 20)
    model.add(op_vars[(1, 0)]["start"] == 30)
    sc = SoftConstraint(
        natural_language="evite la nuit",
        category="avoid_machine_during_period",
        parameters={"machine_reference": "M0", "period_type": "night"},
        weight_hint=0.5,
        weight_rationale="x",
        confidence="medium",
    )
    sp = translate_avoid_machine_during_period(
        model,
        instance=instance,
        op_vars=op_vars,
        horizon=horizon,
        constraint=sc,
        machine_name_to_id={"M0": 0},
        period_start=50,
        period_end=80,
    )
    assert sp is not None
    # On minimise la penalite seule
    model.minimize(sp.var)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(sp.var) == 0


def test_avoid_machine_during_period_returns_none_for_unknown_machine() -> None:
    instance = _instance_two_jobs_with_deadlines((None, None))
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="x",
        category="avoid_machine_during_period",
        parameters={"machine_reference": "MACHINE_INCONNUE"},
        weight_hint=0.5,
        weight_rationale="x",
        confidence="low",
    )
    sp = translate_avoid_machine_during_period(
        model,
        instance=instance,
        op_vars=op_vars,
        horizon=100,
        constraint=sc,
        machine_name_to_id={"M0": 0},
        period_start=10,
        period_end=20,
    )
    assert sp is None


# ---------- Translator : encourage_early_completion ----------


def test_encourage_early_completion_minimizes_sum_of_ends() -> None:
    """La penalite = somme des fins ; minimise force chaque op a finir tot."""
    instance = _instance_two_jobs_with_deadlines((None, None))
    model = cp_model.CpModel()
    horizon = 100
    op_vars = _build_op_vars(model, instance, horizon)
    sc = SoftConstraint(
        natural_language="finis tot",
        category="other",
        parameters={"kind": "encourage_early_completion"},
        weight_hint=1.0,
        weight_rationale="x",
        confidence="high",
    )
    sp = translate_encourage_early_completion(
        model, instance=instance, op_vars=op_vars, horizon=horizon, constraint=sc
    )
    assert sp is not None
    # On minimise la penalite
    model.minimize(sp.var)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    # 2 jobs, durees 5 chacun, no_overlap sur m0 -> J0 [0,5], J1 [5,10]
    # Somme des ends = 5 + 10 = 15.
    assert solver.value(sp.var) == 15


# ---------- Dispatcher ----------


def test_dispatcher_skips_unsupported_categories() -> None:
    instance = _instance_two_jobs_with_deadlines((None, None))
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    # `prefer_machine_over_other` necessite la machine en variable de decision
    # (refactor non livre en V1) — le dispatcher doit skip silencieusement.
    constraints = [
        SoftConstraint(
            natural_language="privilegier TOUR-01 sur TOUR-02",
            category="prefer_machine_over_other",
            parameters={
                "preferred_machine_reference": "TOUR-01",
                "over_machine_reference": "TOUR-02",
            },
            weight_hint=0.5,
            weight_rationale="x",
            confidence="medium",
        ),
    ]
    out = translate_soft_constraints(
        model,
        instance=instance,
        op_vars=op_vars,
        horizon=100,
        soft_constraints=constraints,
    )
    assert out == []


# ---------- Integration solver : 5 hard + 3 soft cohabitent ----------


def test_solver_with_tardiness_changes_schedule() -> None:
    """Demontre que la soft constraint change la solution vs makespan seul."""
    # 1 machine, 2 jobs dur 5. Sans soft : makespan 10, ordre indifferent.
    # Avec tardiness pondere, le job avec la deadline serree finit en premier.
    instance = WorkshopInstance(
        name="tardiness_demo",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5),
                ],
                deadline=100,  # large
                client="Bosch",
            ),
            Job(
                job_id=1,
                operations=[
                    Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5),
                ],
                deadline=5,  # serre : doit finir avant 5
                client="Safran",
            ),
        ],
        machines=[Machine(machine_id=0)],
    )

    def builder(*, model, instance, op_vars, horizon):
        return translate_soft_constraints(
            model,
            instance=instance,
            op_vars=op_vars,
            horizon=horizon,
            soft_constraints=[
                SoftConstraint(
                    natural_language="OF Safran avant deadline",
                    category="client_priority",
                    parameters={"client_reference": "Safran"},
                    weight_hint=1.0,
                    weight_rationale="critique",
                    confidence="high",
                )
            ],
        )

    solver = JSSPSolver(time_limit_seconds=5.0)
    result = solver.solve(instance, soft_penalty_builder=builder)
    assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    # Avec la pression sur Safran, J1 (Safran, deadline=5) doit finir <= 5
    j1_end = next(a.end for a in result.schedule if a.job_id == 1)
    assert j1_end <= 5
    # Le makespan brut reste 10 (deux ops dur 5 sur 1 machine)
    assert result.makespan == 10


def test_solver_with_no_soft_unchanged_behavior() -> None:
    """Sans soft_penalty_builder, comportement legacy = makespan seul."""
    instance = WorkshopInstance(
        name="legacy",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=3),
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
    )
    solver = JSSPSolver(time_limit_seconds=5.0)
    result = solver.solve(instance)
    assert result.status is SolverStatus.OPTIMAL
    assert result.makespan == 3


def test_solver_5_hard_3_soft_cohabitate() -> None:
    """Cohabitation : NoOverlap + Precedence + Setup + Calendar + Operator + 3 soft."""
    instance = WorkshopInstance(
        name="cohabitation_5hard_3soft",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(
                        job_id=0,
                        sequence_idx=0,
                        machine_id=0,
                        duration=5,
                        family_id=0,
                        qualified_operator_ids=[0],
                    ),
                    Operation(
                        job_id=0,
                        sequence_idx=1,
                        machine_id=1,
                        duration=4,
                        family_id=0,
                        qualified_operator_ids=[0],
                    ),
                ],
                deadline=30,
                client="Safran",
            ),
            Job(
                job_id=1,
                operations=[
                    Operation(
                        job_id=1,
                        sequence_idx=0,
                        machine_id=0,
                        duration=3,
                        family_id=1,
                        qualified_operator_ids=[0, 1],
                    ),
                ],
                deadline=20,
                client="Bosch",
            ),
        ],
        machines=[Machine(machine_id=0), Machine(machine_id=1)],
        n_operators=2,
        transition_matrix=[[0, 5], [5, 0]],
        shared_resources=[
            SharedResourceSpec(resource_name="aspiration", machine_ids=[0, 1], max_concurrent=1)
        ],
        machine_unavailability=[MachineUnavailabilitySpec(machine_id=0, periods=[(0, 2)])],
    )

    def builder(*, model, instance, op_vars, horizon):
        return translate_soft_constraints(
            model,
            instance=instance,
            op_vars=op_vars,
            horizon=horizon,
            soft_constraints=[
                SoftConstraint(
                    natural_language="OF Safran prioritaires",
                    category="client_priority",
                    parameters={"client_reference": "Safran"},
                    weight_hint=0.6,
                    weight_rationale="x",
                    confidence="high",
                ),
                SoftConstraint(
                    natural_language="evite m0 nuit",
                    category="avoid_machine_during_period",
                    parameters={"machine_reference": "M0", "period_type": "night"},
                    weight_hint=0.4,
                    weight_rationale="x",
                    confidence="medium",
                ),
                SoftConstraint(
                    natural_language="finis tot",
                    category="other",
                    parameters={"kind": "encourage_early_completion"},
                    weight_hint=0.2,
                    weight_rationale="x",
                    confidence="high",
                ),
            ],
            machine_name_to_id={"M0": 0, "M1": 1},
            period_resolver={"night": (50, 80)},
        )

    solver = JSSPSolver(time_limit_seconds=10.0)
    result = solver.solve(instance, soft_penalty_builder=builder)
    assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert result.makespan is not None
    assert result.makespan > 0
    # Le pattern weighted_objective doit etre dans patterns_applied
    assert "weighted_objective" in result.patterns_applied


# ---------- Translator : limit_ops_per_day_on_machine ----------


def test_limit_ops_per_day_zero_excess_when_under_threshold() -> None:
    """3 ops sur m0, max=5 par jour : pas de penalite."""
    instance = WorkshopInstance(
        name="limit_ok",
        jobs=[
            Job(
                job_id=j,
                operations=[Operation(job_id=j, sequence_idx=0, machine_id=0, duration=2)],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="max 5 changements/jour",
        category="limit_setups_per_day_on_machine",
        parameters={"machine_reference": "M0", "max_setups_per_day": 5},
        weight_hint=0.7,
        weight_rationale="x",
        confidence="high",
    )
    sp = translate_limit_ops_per_day_on_machine(
        model,
        instance=instance,
        op_vars=op_vars,
        horizon=100,
        constraint=sc,
        machine_name_to_id={"M0": 0},
        day_offsets=[(0, 100)],
    )
    assert sp is not None
    model.minimize(sp.var)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(sp.var) == 0


def test_limit_ops_per_day_returns_none_for_unknown_machine() -> None:
    instance = WorkshopInstance(
        name="x",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=2)],
            )
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="x",
        category="limit_setups_per_day_on_machine",
        parameters={"machine_reference": "INCONNUE", "max_setups_per_day": 3},
        weight_hint=0.5,
        weight_rationale="x",
        confidence="medium",
    )
    sp = translate_limit_ops_per_day_on_machine(
        model,
        instance=instance,
        op_vars=op_vars,
        horizon=100,
        constraint=sc,
        machine_name_to_id={"M0": 0},
        day_offsets=[(0, 100)],
    )
    assert sp is None


# ---------- Translator : prefer_grouping_by_family ----------


def test_grouping_by_family_zero_when_no_multi_op_group() -> None:
    """Un seul op par (machine, family) => spread vide => None."""
    instance = WorkshopInstance(
        name="grp_single",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=2, family_id=0)
                ],
            ),
            Job(
                job_id=1,
                operations=[
                    Operation(job_id=1, sequence_idx=0, machine_id=0, duration=2, family_id=1)
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="grouper",
        category="prefer_grouping_by_material",
        parameters={},
        weight_hint=0.3,
        weight_rationale="x",
        confidence="medium",
    )
    sp = translate_prefer_grouping_by_family(
        model, instance=instance, op_vars=op_vars, horizon=100, constraint=sc
    )
    assert sp is None


def test_grouping_by_family_minimizes_spread() -> None:
    """3 ops m0 family 0 (dur 2) : minimiser spread => collees [0-2, 2-4, 4-6] => spread=6."""
    instance = WorkshopInstance(
        name="grp_minimize",
        jobs=[
            Job(
                job_id=j,
                operations=[
                    Operation(job_id=j, sequence_idx=0, machine_id=0, duration=2, family_id=0)
                ],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="grouper",
        category="prefer_grouping_by_material",
        parameters={},
        weight_hint=1.0,
        weight_rationale="x",
        confidence="high",
    )
    sp = translate_prefer_grouping_by_family(
        model, instance=instance, op_vars=op_vars, horizon=100, constraint=sc
    )
    assert sp is not None
    model.minimize(sp.var)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    # 3 ops dur 2 sur 1 machine, no_overlap : ends 2, 4, 6, starts 0, 2, 4 => spread = 6 - 0 = 6
    assert solver.value(sp.var) == 6


# ---------- Translator : prefer_grouping_by_client ----------


def test_grouping_by_client_filters_and_returns_none_when_no_client() -> None:
    instance = _instance_two_jobs_with_deadlines((None, None))  # clients = (None, None)
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="grouper Safran",
        category="prefer_grouping_by_client",
        parameters={"client_reference": "Safran"},
        weight_hint=0.5,
        weight_rationale="x",
        confidence="medium",
    )
    sp = translate_prefer_grouping_by_client(
        model, instance=instance, op_vars=op_vars, horizon=100, constraint=sc
    )
    assert sp is None  # aucun job avec client = "Safran"


def test_grouping_by_client_aggregates_per_machine_per_client() -> None:
    """4 jobs, 2 par client, 1 machine. Spread par client = end_dernier - start_premier."""
    instance = WorkshopInstance(
        name="grp_clients",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=2)],
                client="Safran",
            ),
            Job(
                job_id=1,
                operations=[Operation(job_id=1, sequence_idx=0, machine_id=0, duration=2)],
                client="Safran",
            ),
            Job(
                job_id=2,
                operations=[Operation(job_id=2, sequence_idx=0, machine_id=0, duration=2)],
                client="Bosch",
            ),
            Job(
                job_id=3,
                operations=[Operation(job_id=3, sequence_idx=0, machine_id=0, duration=2)],
                client="Bosch",
            ),
        ],
        machines=[Machine(machine_id=0)],
    )
    model = cp_model.CpModel()
    op_vars = _build_op_vars(model, instance, horizon=100)
    sc = SoftConstraint(
        natural_language="grouper par client",
        category="prefer_grouping_by_client",
        parameters={},  # tous clients
        weight_hint=1.0,
        weight_rationale="x",
        confidence="high",
    )
    sp = translate_prefer_grouping_by_client(
        model, instance=instance, op_vars=op_vars, horizon=100, constraint=sc
    )
    assert sp is not None
    # Minimiser le spread total : Safran [0,2]+[2,4] => spread 4 ; Bosch [4,6]+[6,8] => spread 4
    # OU n'importe quelle alternance regroupee. Total min = 4+4 = 8.
    model.minimize(sp.var)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.value(sp.var) == 8


# ---------- Cohabitation 5 hard + 5 soft (critere de sortie 1.6) ----------


def test_solver_5_hard_5_soft_cohabitate() -> None:
    """Critere de sortie 1.6 : 5 soft + 5 hard cohabitent.

    Hard : NoOverlap, Precedence, Setup-dependent, Calendar (unavailability),
    Operator (qualifications), SharedResource — > 5 patterns hard actifs.
    Soft : tardiness (client_priority), avoid_period, encourage_early_completion,
    limit_ops_per_day, prefer_grouping_by_family — 5 soft simultanes.
    """
    instance = WorkshopInstance(
        name="cohab_5h_5s",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(
                        job_id=0,
                        sequence_idx=0,
                        machine_id=0,
                        duration=4,
                        family_id=0,
                        qualified_operator_ids=[0],
                    ),
                    Operation(
                        job_id=0,
                        sequence_idx=1,
                        machine_id=1,
                        duration=3,
                        family_id=0,
                        qualified_operator_ids=[0],
                    ),
                ],
                deadline=40,
                client="Safran",
            ),
            Job(
                job_id=1,
                operations=[
                    Operation(
                        job_id=1,
                        sequence_idx=0,
                        machine_id=0,
                        duration=3,
                        family_id=1,
                        qualified_operator_ids=[0, 1],
                    ),
                ],
                deadline=30,
                client="Bosch",
            ),
            Job(
                job_id=2,
                operations=[
                    Operation(
                        job_id=2,
                        sequence_idx=0,
                        machine_id=0,
                        duration=2,
                        family_id=0,
                        qualified_operator_ids=[0, 1],
                    ),
                ],
                deadline=50,
                client="Safran",
            ),
        ],
        machines=[Machine(machine_id=0), Machine(machine_id=1)],
        n_operators=2,
        transition_matrix=[[0, 5], [5, 0]],
        shared_resources=[
            SharedResourceSpec(resource_name="aspiration", machine_ids=[0, 1], max_concurrent=1)
        ],
        machine_unavailability=[MachineUnavailabilitySpec(machine_id=0, periods=[(0, 1)])],
    )

    def builder(*, model, instance, op_vars, horizon):
        return translate_soft_constraints(
            model,
            instance=instance,
            op_vars=op_vars,
            horizon=horizon,
            soft_constraints=[
                SoftConstraint(
                    natural_language="OF Safran prioritaires",
                    category="client_priority",
                    parameters={"client_reference": "Safran"},
                    weight_hint=0.6,
                    weight_rationale="x",
                    confidence="high",
                ),
                SoftConstraint(
                    natural_language="evite m0 nuit",
                    category="avoid_machine_during_period",
                    parameters={"machine_reference": "M0", "period_type": "night"},
                    weight_hint=0.3,
                    weight_rationale="x",
                    confidence="medium",
                ),
                SoftConstraint(
                    natural_language="finis tot",
                    category="other",
                    parameters={"kind": "encourage_early_completion"},
                    weight_hint=0.2,
                    weight_rationale="x",
                    confidence="high",
                ),
                SoftConstraint(
                    natural_language="max 4 ops/jour sur m0",
                    category="limit_setups_per_day_on_machine",
                    parameters={"machine_reference": "M0", "max_setups_per_day": 4},
                    weight_hint=0.5,
                    weight_rationale="x",
                    confidence="medium",
                ),
                SoftConstraint(
                    natural_language="grouper meme matiere",
                    category="prefer_grouping_by_material",
                    parameters={},
                    weight_hint=0.4,
                    weight_rationale="x",
                    confidence="medium",
                ),
            ],
            machine_name_to_id={"M0": 0, "M1": 1},
            period_resolver={"night": (60, 90)},
            day_offsets=[(0, 30), (30, 60), (60, 90)],
        )

    solver = JSSPSolver(time_limit_seconds=15.0)
    result = solver.solve(instance, soft_penalty_builder=builder)
    assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert result.makespan is not None
    assert result.makespan > 0
    assert "weighted_objective" in result.patterns_applied
