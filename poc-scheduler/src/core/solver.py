"""Solveur CP-SAT pour le Job-Shop Scheduling Problem (JSSP) classique.

Étape 0.3 — version basique :
- Une opération par machine et par job.
- Précédence séquentielle dans les gammes.
- NoOverlap par machine.
- Objectif : minimisation du makespan.

Pas encore de : sequence-dependent setup, qualified operators, shared resources,
calendars, soft constraints. Ces patterns arrivent à l'étape 0.6.
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
from src.core.patterns import (
    add_no_overlap_machine,
    add_precedence_in_job,
    make_makespan_objective,
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

    @property
    def has_solution(self) -> bool:
        return self.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)

    def gap_percent(self, best_known: int) -> float | None:
        """Calcule le gap relatif vs un optimum connu (en %).

        Returns:
            `100 * (found - best_known) / best_known`, ou None si pas de solution
            ou `best_known <= 0`.
        """
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
    """Solveur CP-SAT pour JSSP basique."""

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

        Args:
            instance: Instance JSSP à résoudre.

        Returns:
            `SolverResult` avec status, makespan, planning et statistiques.
        """
        model = cp_model.CpModel()
        horizon = self._compute_horizon(instance)

        op_vars: dict[tuple[int, int], dict[str, Any]] = {}
        intervals_per_machine: dict[int, list[Any]] = {m.machine_id: [] for m in instance.machines}

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
                }
                intervals_per_machine[op.machine_id].append(interval)

        for job in instance.jobs:
            ordered = sorted(job.operations, key=lambda o: o.sequence_idx)
            end_vars = [op_vars[(job.job_id, op.sequence_idx)]["end"] for op in ordered]
            start_vars = [op_vars[(job.job_id, op.sequence_idx)]["start"] for op in ordered]
            add_precedence_in_job(model, end_vars, start_vars)

        for intervals in intervals_per_machine.values():
            add_no_overlap_machine(model, intervals)

        last_op_ends = [
            op_vars[(job.job_id, max(op.sequence_idx for op in job.operations))]["end"]
            for job in instance.jobs
        ]
        make_makespan_objective(model, last_op_ends, horizon)

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
        )

    @staticmethod
    def _compute_horizon(instance: WorkshopInstance) -> int:
        """Borne sup naïve mais sûre : somme de toutes les durées."""
        return sum(op.duration for job in instance.jobs for op in job.operations)


# ---------- Validation ----------


def validate_schedule(
    instance: WorkshopInstance,
    schedule: Sequence[ScheduleAssignment],
) -> list[str]:
    """Vérifie qu'un planning respecte toutes les contraintes du JSSP de base.

    Sert aux tests, et plus tard au trust layer (étape 2.x).

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
