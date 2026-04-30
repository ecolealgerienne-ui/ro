"""Simulation operationnelle — analyse post-hoc d'un schedule.

Module **vertical-agnostic** : calcule des metriques operationnelles
universelles (fragmentation, micro-pauses, setup/utile, transitions) qui
temoignent de la qualite REELLE d'un planning au-dela du makespan.

Le solveur minimise le makespan ; il ne penalise pas (sauf via setup-pattern)
les pieces fragmentees ou les pauses ridiculement courtes. La simulation
attrape ces signaux qu'un chef d'atelier humain refuserait.

Pipeline :
    schedule + thresholds -> SimulationReport (metrics + violations)

Voir `src/verticals/<vertical>/simulation_config.py` pour les seuils metier.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from itertools import pairwise
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.models import WorkshopInstance
from src.core.solver import ScheduleAssignment, SolverResult


class ViolationSeverity(StrEnum):
    WARN = "WARN"
    REJECT = "REJECT"


class SimulationViolation(BaseModel):
    """Une regle metier violee par le planning."""

    model_config = ConfigDict(frozen=True)

    rule: str
    severity: ViolationSeverity
    target: str = Field(..., description="Sur quoi porte la violation (ex: 'machine_3', 'job_12').")
    raw_value: float
    threshold: float
    description: str


class MachineMetrics(BaseModel):
    """Metriques agregees pour une machine."""

    model_config = ConfigDict(frozen=True)

    machine_id: int
    n_ops: int = Field(..., ge=0)
    productive_time: int = Field(..., ge=0)
    setup_time: int = Field(..., ge=0)
    idle_time: int = Field(..., ge=0)
    setup_ratio: float = Field(..., ge=0.0, le=1.0)
    micro_pause_count: int = Field(..., ge=0)
    family_transitions: int = Field(..., ge=0)


class JobMetrics(BaseModel):
    """Metriques agregees pour un job (= une commande)."""

    model_config = ConfigDict(frozen=True)

    job_id: int
    duration_sum: int = Field(..., ge=0)
    span: int = Field(..., ge=0, description="end_dernier - start_premier.")
    fragmentation_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="(span - duration_sum) / span : 0 = aucune attente, 1 = que de l'attente.",
    )


class SimulationVerdict(StrEnum):
    """Decision finale du simulateur sur le planning."""

    ACCEPT = "ACCEPT"
    WARN = "WARN"
    REJECT = "REJECT"


class SimulationReport(BaseModel):
    """Resultat complet de la simulation operationnelle."""

    model_config = ConfigDict(frozen=True)

    verdict: SimulationVerdict
    machines: list[MachineMetrics]
    jobs: list[JobMetrics]
    violations: list[SimulationViolation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _verdict_consistent_with_violations(self) -> SimulationReport:
        has_reject = any(v.severity is ViolationSeverity.REJECT for v in self.violations)
        has_warn = any(v.severity is ViolationSeverity.WARN for v in self.violations)
        expected = (
            SimulationVerdict.REJECT
            if has_reject
            else SimulationVerdict.WARN
            if has_warn
            else SimulationVerdict.ACCEPT
        )
        if self.verdict is not expected:
            raise ValueError(
                f"verdict {self.verdict} incoherent avec les violations (attendu : {expected})"
            )
        return self


# ---------- Calculs ----------


_EMPTY_MATRIX: Final[list[list[int]]] = []


def _ops_per_machine(
    instance: WorkshopInstance,
    schedule: Sequence[ScheduleAssignment],
) -> dict[int, list[ScheduleAssignment]]:
    """Regroupe les assignments par machine, tries par start croissant."""
    by_machine: dict[int, list[ScheduleAssignment]] = {m.machine_id: [] for m in instance.machines}
    for a in schedule:
        by_machine.setdefault(a.machine_id, []).append(a)
    for ops in by_machine.values():
        ops.sort(key=lambda a: a.start)
    return by_machine


def _family_id(instance: WorkshopInstance, assignment: ScheduleAssignment) -> int:
    """Recupere le family_id de l'operation pointee par l'assignment."""
    job = instance.jobs[assignment.job_id]
    return job.operations[assignment.sequence_idx].family_id


def _machine_metrics(
    instance: WorkshopInstance,
    machine_id: int,
    ops: list[ScheduleAssignment],
    *,
    micro_pause_threshold: int,
) -> MachineMetrics:
    matrix = instance.transition_matrix or _EMPTY_MATRIX
    productive = sum(a.end - a.start for a in ops)
    setup = 0
    transitions = 0
    micro_pauses = 0

    for prev, curr in pairwise(ops):
        gap = curr.start - prev.end
        if 0 < gap < micro_pause_threshold:
            micro_pauses += 1
        if matrix:
            fam_prev = _family_id(instance, prev)
            fam_curr = _family_id(instance, curr)
            if fam_prev != fam_curr:
                transitions += 1
                setup += matrix[fam_prev][fam_curr]

    span = (ops[-1].end - ops[0].start) if ops else 0
    idle = max(0, span - productive)
    total = productive + setup
    setup_ratio = (setup / total) if total > 0 else 0.0

    return MachineMetrics(
        machine_id=machine_id,
        n_ops=len(ops),
        productive_time=productive,
        setup_time=setup,
        idle_time=idle,
        setup_ratio=setup_ratio,
        micro_pause_count=micro_pauses,
        family_transitions=transitions,
    )


def _job_metrics(instance: WorkshopInstance, schedule: Sequence[ScheduleAssignment]) -> list[JobMetrics]:
    by_job: dict[int, list[ScheduleAssignment]] = {}
    for a in schedule:
        by_job.setdefault(a.job_id, []).append(a)
    metrics: list[JobMetrics] = []
    for job in instance.jobs:
        ops = sorted(by_job.get(job.job_id, []), key=lambda a: a.start)
        if not ops:
            continue
        duration_sum = sum(a.end - a.start for a in ops)
        span = ops[-1].end - ops[0].start
        frag = ((span - duration_sum) / span) if span > 0 else 0.0
        metrics.append(
            JobMetrics(
                job_id=job.job_id,
                duration_sum=duration_sum,
                span=span,
                fragmentation_ratio=max(0.0, min(1.0, frag)),
            )
        )
    return metrics


def _violations(
    machines: list[MachineMetrics],
    jobs: list[JobMetrics],
    *,
    max_setup_ratio: float,
    max_micro_pauses_per_machine: int,
    max_job_fragmentation: float,
    reject_setup_ratio: float,
) -> list[SimulationViolation]:
    out: list[SimulationViolation] = []
    for m in machines:
        if m.setup_ratio > reject_setup_ratio:
            out.append(
                SimulationViolation(
                    rule="setup_ratio_critical",
                    severity=ViolationSeverity.REJECT,
                    target=f"machine_{m.machine_id}",
                    raw_value=m.setup_ratio,
                    threshold=reject_setup_ratio,
                    description=(
                        f"Machine {m.machine_id} : setup ratio {m.setup_ratio:.2%} > "
                        f"seuil critique {reject_setup_ratio:.2%}"
                    ),
                )
            )
        elif m.setup_ratio > max_setup_ratio:
            out.append(
                SimulationViolation(
                    rule="setup_ratio_high",
                    severity=ViolationSeverity.WARN,
                    target=f"machine_{m.machine_id}",
                    raw_value=m.setup_ratio,
                    threshold=max_setup_ratio,
                    description=(
                        f"Machine {m.machine_id} : setup ratio {m.setup_ratio:.2%} > "
                        f"seuil {max_setup_ratio:.2%}"
                    ),
                )
            )
        if m.micro_pause_count > max_micro_pauses_per_machine:
            out.append(
                SimulationViolation(
                    rule="micro_pauses_excess",
                    severity=ViolationSeverity.WARN,
                    target=f"machine_{m.machine_id}",
                    raw_value=float(m.micro_pause_count),
                    threshold=float(max_micro_pauses_per_machine),
                    description=(
                        f"Machine {m.machine_id} : {m.micro_pause_count} micro-pauses > "
                        f"seuil {max_micro_pauses_per_machine}"
                    ),
                )
            )
    for j in jobs:
        if j.fragmentation_ratio > max_job_fragmentation:
            out.append(
                SimulationViolation(
                    rule="job_fragmentation_high",
                    severity=ViolationSeverity.WARN,
                    target=f"job_{j.job_id}",
                    raw_value=j.fragmentation_ratio,
                    threshold=max_job_fragmentation,
                    description=(
                        f"Job {j.job_id} : fragmentation {j.fragmentation_ratio:.2%} > "
                        f"seuil {max_job_fragmentation:.2%}"
                    ),
                )
            )
    return out


def simulate_schedule(
    instance: WorkshopInstance,
    result: SolverResult,
    *,
    micro_pause_threshold: int,
    max_setup_ratio: float,
    reject_setup_ratio: float,
    max_micro_pauses_per_machine: int,
    max_job_fragmentation: float,
) -> SimulationReport:
    """Analyse post-hoc d'un schedule, agnostique a la verticale.

    Args:
        instance: instance d'origine (pour family_id et transition_matrix).
        result: resultat du solveur (la simulation s'applique sur `result.schedule`).
        micro_pause_threshold: une "pause" inferieure a ce seuil est comptee
            comme micro-pause (penalisee).
        max_setup_ratio: au-dela de ce ratio setup/total, WARN.
        reject_setup_ratio: au-dela de ce ratio, REJECT (planning juge non viable).
        max_micro_pauses_per_machine: au-dela de N micro-pauses, WARN.
        max_job_fragmentation: au-dela de ce ratio, WARN sur le job.

    Returns:
        `SimulationReport` avec metriques + violations + verdict.
    """
    if reject_setup_ratio < max_setup_ratio:
        raise ValueError(
            f"reject_setup_ratio ({reject_setup_ratio}) doit etre >= "
            f"max_setup_ratio ({max_setup_ratio})"
        )

    by_machine = _ops_per_machine(instance, result.schedule)
    machines = [
        _machine_metrics(
            instance, m_id, ops, micro_pause_threshold=micro_pause_threshold
        )
        for m_id, ops in sorted(by_machine.items())
    ]
    jobs = _job_metrics(instance, result.schedule)
    violations = _violations(
        machines,
        jobs,
        max_setup_ratio=max_setup_ratio,
        max_micro_pauses_per_machine=max_micro_pauses_per_machine,
        max_job_fragmentation=max_job_fragmentation,
        reject_setup_ratio=reject_setup_ratio,
    )

    has_reject = any(v.severity is ViolationSeverity.REJECT for v in violations)
    has_warn = any(v.severity is ViolationSeverity.WARN for v in violations)
    verdict = (
        SimulationVerdict.REJECT
        if has_reject
        else SimulationVerdict.WARN
        if has_warn
        else SimulationVerdict.ACCEPT
    )

    return SimulationReport(
        verdict=verdict,
        machines=machines,
        jobs=jobs,
        violations=violations,
    )
