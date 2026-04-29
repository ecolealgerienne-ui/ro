"""Solveur CP-SAT pour Job-Shop Scheduling avec contraintes industrielles.

Étape 1.1c — intégration des patterns avancés :
- JSSP de base : NoOverlap par machine, Precedence intra-job, Makespan
- Setup-dependent : si `instance.transition_matrix` non vide
- Qualified operator : si `instance.n_operators > 0` et qualifications présentes
- Shared resource exclusion : si `instance.shared_resources` non vide
- Machine unavailability : si `instance.machine_unavailability` non vide

Les patterns sont activés conditionnellement selon les `has_*` properties de
`WorkshopInstance`. Une instance JSSP "nue" (Taillard, mini-tests) reste
résolue exactement comme avant l'étape 1.1c.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from ortools.sat.python import cp_model
from pydantic import BaseModel, ConfigDict, Field

from src.core.models import WorkshopInstance
from src.core.pattern import (
    MakespanObjectivePattern,
    NoOverlapMachinePattern,
    PrecedenceInJobPattern,
    QualifiedOperatorPattern,
    SequenceDependentSetupPattern,
    SharedResourceExclusionPattern,
    UnavailableIntervalsPattern,
)

_logger = logging.getLogger(__name__)


# ---------- Types de résultat ----------


class SolverStatus(StrEnum):
    """Mappage simplifié des statuts CP-SAT."""

    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    MODEL_INVALID = "MODEL_INVALID"
    UNKNOWN = "UNKNOWN"


class ScheduleAssignment(BaseModel):
    """Affectation d'une opération sur une machine à un instant donné."""

    model_config = ConfigDict(frozen=True)

    job_id: int = Field(..., ge=0)
    sequence_idx: int = Field(..., ge=0)
    machine_id: int = Field(..., ge=0)
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)


class SolverResult(BaseModel):
    """Résultat d'un solving CP-SAT."""

    model_config = ConfigDict(frozen=True)

    instance_name: str
    status: SolverStatus
    makespan: int | None = None
    objective_bound: float | None = None
    schedule: list[ScheduleAssignment] = Field(default_factory=list)
    solve_time_seconds: float = Field(..., ge=0.0)
    patterns_applied: list[str] = Field(default_factory=list)

    @property
    def has_solution(self) -> bool:
        return self.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)

    def gap_percent(self, best_known: int) -> float | None:
        if self.makespan is None or best_known <= 0:
            return None
        return 100.0 * (self.makespan - best_known) / best_known


# ---------- Solveur ----------


_STATUS_MAP: dict[int, SolverStatus] = {
    cp_model.OPTIMAL: SolverStatus.OPTIMAL,
    cp_model.FEASIBLE: SolverStatus.FEASIBLE,
    cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
    cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
    cp_model.UNKNOWN: SolverStatus.UNKNOWN,
}


class JSSPSolver:
    """Solveur CP-SAT pour JSSP avec contraintes industrielles optionnelles."""

    def __init__(
        self,
        time_limit_seconds: float = 60.0,
        num_workers: int = 8,
        log_search_progress: bool = False,
    ) -> None:
        if time_limit_seconds <= 0:
            raise ValueError(f"time_limit_seconds doit être > 0, reçu {time_limit_seconds}")
        if num_workers < 1:
            raise ValueError(f"num_workers doit être >= 1, reçu {num_workers}")
        self.time_limit_seconds = time_limit_seconds
        self.num_workers = num_workers
        self.log_search_progress = log_search_progress

    def solve(self, instance: WorkshopInstance) -> SolverResult:
        """Construit le modèle CP-SAT et résout.

        Applique les patterns selon les `has_*` properties de l'instance :
        toujours NoOverlap + Precedence + Makespan, conditionnellement les
        patterns industriels.
        """
        model = cp_model.CpModel()
        horizon = self._compute_horizon(instance)
        patterns_applied: list[str] = []

        # --- Variables par opération ---
        op_vars: dict[tuple[int, int], dict[str, Any]] = {}
        intervals_per_machine: dict[int, list[Any]] = {m.machine_id: [] for m in instance.machines}
        ops_per_machine: dict[int, list[tuple[int, int]]] = {m.machine_id: [] for m in instance.machines}

        for job in instance.jobs:
            for op in job.operations:
                key = (job.job_id, op.sequence_idx)
                start = model.new_int_var(0, horizon, f"s_{job.job_id}_{op.sequence_idx}")
                end = model.new_int_var(0, horizon, f"e_{job.job_id}_{op.sequence_idx}")
                interval = model.new_interval_var(
                    start, op.duration, end, f"i_{job.job_id}_{op.sequence_idx}"
                )
                op_vars[key] = {
                    "start": start,
                    "end": end,
                    "interval": interval,
                    "machine_id": op.machine_id,
                    "duration": op.duration,
                    "family_id": op.family_id,
                    "qualified_operator_ids": op.qualified_operator_ids,
                }
                intervals_per_machine[op.machine_id].append(interval)
                ops_per_machine[op.machine_id].append(key)

        # --- Précédence intra-job ---
        precedence_pattern = PrecedenceInJobPattern()
        for job in instance.jobs:
            ordered = sorted(job.operations, key=lambda o: o.sequence_idx)
            end_vars = [op_vars[(job.job_id, op.sequence_idx)]["end"] for op in ordered]
            start_vars = [op_vars[(job.job_id, op.sequence_idx)]["start"] for op in ordered]
            precedence_pattern.apply(model, end_vars=end_vars, start_vars=start_vars)
        patterns_applied.append(PrecedenceInJobPattern.name)

        # --- Indisponibilités machines (à fusionner avec NoOverlap) ---
        unavail_per_machine: dict[int, list[Any]] = {}
        if instance.has_unavailability:
            unavail_pattern = UnavailableIntervalsPattern()
            for spec in instance.machine_unavailability:
                unavail_per_machine[spec.machine_id] = unavail_pattern.apply(
                    model, periods=spec.periods
                )
            patterns_applied.append(UnavailableIntervalsPattern.name)

        # --- NoOverlap par machine (toujours, fusionne ops + indispo) ---
        no_overlap_pattern = NoOverlapMachinePattern()
        for machine_id, intervals in intervals_per_machine.items():
            combined = intervals + unavail_per_machine.get(machine_id, [])
            no_overlap_pattern.apply(model, intervals=combined)
        patterns_applied.append(NoOverlapMachinePattern.name)

        # --- Setup-dependent (si matrice non vide), en plus du NoOverlap ---
        if instance.has_setup_constraints:
            setup_pattern = SequenceDependentSetupPattern()
            for machine_id, op_keys in ops_per_machine.items():
                if len(op_keys) <= 1:
                    continue
                starts = [op_vars[k]["start"] for k in op_keys]
                ends = [op_vars[k]["end"] for k in op_keys]
                family_ids = [op_vars[k]["family_id"] for k in op_keys]
                setup_pattern.apply(
                    model,
                    starts=starts,
                    ends=ends,
                    family_ids=family_ids,
                    transition_matrix=instance.transition_matrix,
                )
            patterns_applied.append(SequenceDependentSetupPattern.name)

        # --- Qualified operator (instance-level) ---
        if instance.has_operator_constraints:
            all_starts: list[Any] = []
            all_ends: list[Any] = []
            all_durations: list[int] = []
            all_quals: list[list[int]] = []
            for job in instance.jobs:
                for op in job.operations:
                    v = op_vars[(job.job_id, op.sequence_idx)]
                    all_starts.append(v["start"])
                    all_ends.append(v["end"])
                    all_durations.append(int(v["duration"]))
                    all_quals.append(list(v["qualified_operator_ids"]))
            QualifiedOperatorPattern().apply(
                model,
                starts=all_starts,
                ends=all_ends,
                durations=all_durations,
                qualifications=all_quals,
                n_operators=instance.n_operators,
            )
            patterns_applied.append(QualifiedOperatorPattern.name)

        # --- Shared resources ---
        if instance.has_shared_resources:
            shared_pattern = SharedResourceExclusionPattern()
            for res in instance.shared_resources:
                allowed_machines = set(res.machine_ids)
                intervals = [
                    op_vars[k]["interval"]
                    for machine_id, keys in ops_per_machine.items()
                    if machine_id in allowed_machines
                    for k in keys
                ]
                shared_pattern.apply(
                    model,
                    intervals=intervals,
                    max_concurrent=res.max_concurrent,
                )
            patterns_applied.append(SharedResourceExclusionPattern.name)

        # --- Makespan objective ---
        last_op_ends = [
            op_vars[(job.job_id, max(op.sequence_idx for op in job.operations))]["end"]
            for job in instance.jobs
        ]
        MakespanObjectivePattern().apply(model, end_vars=last_op_ends, horizon=horizon)
        patterns_applied.append(MakespanObjectivePattern.name)

        # --- Solving ---
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.time_limit_seconds)
        solver.parameters.num_workers = int(self.num_workers)
        solver.parameters.log_search_progress = bool(self.log_search_progress)

        t0 = time.perf_counter()
        status_int = solver.solve(model)
        solve_time = time.perf_counter() - t0

        status = _STATUS_MAP.get(status_int, SolverStatus.UNKNOWN)

        schedule: list[ScheduleAssignment] = []
        makespan: int | None = None
        if status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            makespan = int(solver.objective_value)
            for (job_id, seq_idx), v in op_vars.items():
                schedule.append(
                    ScheduleAssignment(
                        job_id=job_id,
                        sequence_idx=seq_idx,
                        machine_id=v["machine_id"],
                        start=int(solver.value(v["start"])),
                        end=int(solver.value(v["end"])),
                    )
                )
            schedule.sort(key=lambda a: (a.job_id, a.sequence_idx))

        try:
            bound = float(solver.best_objective_bound)
        except (AttributeError, RuntimeError):
            bound = None

        return SolverResult(
            instance_name=instance.name,
            status=status,
            makespan=makespan,
            objective_bound=bound,
            schedule=schedule,
            solve_time_seconds=solve_time,
            patterns_applied=patterns_applied,
        )

    @staticmethod
    def _compute_horizon(instance: WorkshopInstance) -> int:
        """Borne sup naïve : somme des durées + somme des plus grosses transitions par machine.

        Sur-estime volontairement pour laisser de la marge aux setup-dependent
        et aux indisponibilités.
        """
        base = sum(op.duration for job in instance.jobs for op in job.operations)
        if instance.has_setup_constraints and instance.transition_matrix:
            max_setup = max(max(row) for row in instance.transition_matrix)
            base += max_setup * sum(len(job.operations) for job in instance.jobs)
        if instance.has_unavailability:
            base += sum(
                end - start
                for spec in instance.machine_unavailability
                for start, end in spec.periods
            )
        return base


# ---------- Validation ----------


def validate_schedule(
    instance: WorkshopInstance,
    schedule: Sequence[ScheduleAssignment],
) -> list[str]:
    """Vérifie qu'un planning respecte les contraintes du JSSP de base.

    Sert aux tests, et plus tard au trust layer (étape 2.x).

    Note : ne valide pas encore les contraintes industrielles avancées
    (setup-dependent, opérateur, ressource partagée, indispo). Cette
    extension viendra en étape 1.1d ou 2.

    Returns:
        Liste de messages d'erreur ; vide si tout est valide.
    """
    errors: list[str] = []
    by_op: dict[tuple[int, int], ScheduleAssignment] = {
        (a.job_id, a.sequence_idx): a for a in schedule
    }

    for job in instance.jobs:
        for op in job.operations:
            key = (job.job_id, op.sequence_idx)
            assignment = by_op.get(key)
            if assignment is None:
                errors.append(f"Opération {key} non planifiée")
                continue
            if assignment.machine_id != op.machine_id:
                errors.append(
                    f"Opération {key} : machine {assignment.machine_id} "
                    f"≠ {op.machine_id} attendue"
                )
            if assignment.end - assignment.start != op.duration:
                errors.append(
                    f"Opération {key} : durée {assignment.end - assignment.start} "
                    f"≠ {op.duration} attendue"
                )

    for job in instance.jobs:
        ordered = sorted(job.operations, key=lambda o: o.sequence_idx)
        for i in range(len(ordered) - 1):
            a1 = by_op.get((job.job_id, ordered[i].sequence_idx))
            a2 = by_op.get((job.job_id, ordered[i + 1].sequence_idx))
            if a1 is None or a2 is None:
                continue
            if a1.end > a2.start:
                errors.append(
                    f"Précédence violée job {job.job_id} : op {i} finit à {a1.end} "
                    f"> op {i + 1} démarre à {a2.start}"
                )

    by_machine: dict[int, list[ScheduleAssignment]] = {}
    for a in schedule:
        by_machine.setdefault(a.machine_id, []).append(a)
    for m_id, assigns in by_machine.items():
        sorted_a = sorted(assigns, key=lambda x: x.start)
        for i in range(len(sorted_a) - 1):
            if sorted_a[i].end > sorted_a[i + 1].start:
                errors.append(
                    f"Machine {m_id} : chevauchement entre "
                    f"({sorted_a[i].job_id},{sorted_a[i].sequence_idx}) "
                    f"[{sorted_a[i].start}..{sorted_a[i].end}] et "
                    f"({sorted_a[i + 1].job_id},{sorted_a[i + 1].sequence_idx}) "
                    f"[{sorted_a[i + 1].start}..{sorted_a[i + 1].end}]"
                )

    return errors
