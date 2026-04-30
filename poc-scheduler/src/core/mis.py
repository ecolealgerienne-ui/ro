"""Extraction MIS approximee — Minimal Infeasible Subset.

Module **vertical-agnostic**. Quand le solveur retourne INFEASIBLE, identifie
quels elements de l'instance contribuent a l'infaisabilite. Permet de
diagnostiquer la cause et de generer des actions correctives.

Algorithme V1 (deletion-based, single-element MIS) :

    1. Verifier que l'instance est INFEASIBLE
    2. Pour chaque candidat (job, unavailability period, shared resource) :
        - Construire une copie de l'instance sans cet element
        - Resoudre
        - Si FEASIBLE : cet element est dans le MIS singleton
    3. Retourner la liste des elements detectes + actions correctives suggerees

Limites V1 :
- Detecte uniquement les MIS singletons (un seul element responsable a lui
  seul). Si l'infaisabilite vient de l'interaction de >= 2 elements, le V1
  ne le detecte pas (V2 : deletion par paires, randomized).
- Operations a l'interieur d'un job non removables independamment.

Complexite : O(n_candidats × cout_solve). Pour une instance avec 20 jobs,
5 unavailabilities, 3 shared resources : 28 re-solves. Avec un budget
de 1s/solve sur instances jouets : ~30s. Marquer @slow pour benchmark
serieux ; pour les tests CI utiliser des instances minimales (~3 candidats).

Verticalite :
- L'algorithme et les `MISElement` sont universels (job, unavailability,
  shared_resource sont des concepts du modele engine).
- La verticale peut enrichir le rendering NL via `ExplanationAgent` (3.7) qui
  transforme un `MISReport` en explication chef d'atelier. V1 : le
  `MISReport.to_summary()` engine produit deja un texte exploitable.

Integration : ce module fournit `default_mis_extractor` que
`solve_with_circuit_breaker` (Phase 2.4) peut utiliser comme `mis_extractor`
par defaut.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import WorkshopInstance
from src.core.solver import JSSPSolver, SolverStatus


class MISElementKind(StrEnum):
    """Type d'element identifie comme contribuant a l'infaisabilite."""

    JOB = "JOB"
    MACHINE_UNAVAILABILITY = "MACHINE_UNAVAILABILITY"
    SHARED_RESOURCE = "SHARED_RESOURCE"


class MISElement(BaseModel):
    """Un element de l'instance dont la suppression rend l'instance FEASIBLE.

    Equivalent a un singleton dans le MIS.
    """

    model_config = ConfigDict(frozen=True)

    kind: MISElementKind
    identifier: str = Field(..., min_length=1, description="Identifiant lisible (ex: 'job_5').")
    description: str = Field(..., min_length=1)


class CorrectiveAction(BaseModel):
    """Action corrective suggeree pour rendre l'instance FEASIBLE."""

    model_config = ConfigDict(frozen=True)

    target_kind: MISElementKind
    target_identifier: str
    action_kind: str  # "remove_unavailability" | "defer_job" | "increase_capacity"
    description: str


class MISReport(BaseModel):
    """Rapport complet d'extraction MIS."""

    model_config = ConfigDict(frozen=True)

    initial_status: SolverStatus
    elements: list[MISElement] = Field(default_factory=list)
    suggested_actions: list[CorrectiveAction] = Field(default_factory=list)
    n_attempts: int = 0
    notes: list[str] = Field(default_factory=list)

    @property
    def is_singleton_mis(self) -> bool:
        """True si au moins un element MIS singleton a ete identifie."""
        return len(self.elements) > 0

    def to_summary(self) -> str:
        """Texte court (chef d'atelier-friendly) resumant le MIS et les actions.

        Sert de fallback si pas d'agent LLM disponible. Pour un rendering plus
        riche, passer le `MISReport` a `ExplanationAgent` (3.7) en serialisant
        via `model_dump()`.
        """
        if self.initial_status is not SolverStatus.INFEASIBLE:
            return f"Instance non infaisable (statut initial : {self.initial_status.value})."

        if not self.elements:
            note = (
                "Aucun element singleton n'a ete identifie comme cause unique. "
                "L'infaisabilite provient probablement de l'interaction de plusieurs "
                "contraintes simultanees (V1 ne detecte pas les MIS multi-elements)."
            )
            if self.notes:
                note += " " + " ".join(self.notes)
            return f"INFEASIBLE — analyse approfondie : {note}"

        lines: list[str] = [
            f"INFEASIBLE — {len(self.elements)} element(s) cause(s) identifie(s) :",
        ]
        for el in self.elements:
            lines.append(f"  - [{el.kind.value}] {el.identifier} : {el.description}")
        if self.suggested_actions:
            lines.append("Actions correctives suggerees :")
            for act in self.suggested_actions:
                lines.append(f"  - {act.description}")
        if self.notes:
            lines.append("Notes :")
            for note in self.notes:
                lines.append(f"  - {note}")
        return "\n".join(lines)


# ---------- Helpers : reconstruction d'instance modifiee ----------


def _remove_unavailability_period(
    instance: WorkshopInstance,
    spec_idx: int,
    period_idx: int,
) -> WorkshopInstance:
    """Retourne une copie de l'instance sans la periode (spec_idx, period_idx)."""
    new_unavail = []
    for i, spec in enumerate(instance.machine_unavailability):
        if i == spec_idx:
            new_periods = [p for j, p in enumerate(spec.periods) if j != period_idx]
            if new_periods:
                new_unavail.append(spec.model_copy(update={"periods": new_periods}))
            # else : on retire la spec entiere (plus aucune periode)
        else:
            new_unavail.append(spec)
    return instance.model_copy(update={"machine_unavailability": new_unavail})


def _remove_job(instance: WorkshopInstance, job_idx: int) -> WorkshopInstance:
    """Retourne une copie de l'instance sans le job a l'index `job_idx`."""
    new_jobs = [j for i, j in enumerate(instance.jobs) if i != job_idx]
    return instance.model_copy(update={"jobs": new_jobs})


def _remove_shared_resource(
    instance: WorkshopInstance,
    sr_idx: int,
) -> WorkshopInstance:
    """Retourne une copie de l'instance sans la ressource partagee a `sr_idx`."""
    new_srs = [sr for i, sr in enumerate(instance.shared_resources) if i != sr_idx]
    return instance.model_copy(update={"shared_resources": new_srs})


# ---------- Algorithme principal ----------


def extract_mis_approximate(
    instance: WorkshopInstance,
    *,
    time_limit_per_attempt: float = 5.0,
    max_attempts: int = 50,
    num_workers: int = 4,
) -> MISReport:
    """Extrait un MIS approximé par deletion-based sur les elements singletons.

    Args:
        instance: instance INFEASIBLE a analyser.
        time_limit_per_attempt: budget temps par re-solve. Default 5s.
        max_attempts: borne superieure du nombre de re-solves (garde-fou).
        num_workers: workers CP-SAT par re-solve.

    Returns:
        `MISReport`. Si l'instance n'est pas INFEASIBLE, le report reflete le
        statut reel et n'analyse rien.
    """
    if not instance.jobs:
        return MISReport(
            initial_status=SolverStatus.UNKNOWN,
            notes=["Instance vide (aucun job), MIS non applicable."],
        )

    solver = JSSPSolver(time_limit_seconds=time_limit_per_attempt, num_workers=num_workers)

    # 0. Confirmer l'infaisabilite
    initial = solver.solve(instance)
    if initial.status is not SolverStatus.INFEASIBLE:
        return MISReport(
            initial_status=initial.status,
            notes=[
                f"L'instance n'est pas INFEASIBLE (statut: {initial.status.value}). "
                "Aucune extraction MIS necessaire."
            ],
        )

    elements: list[MISElement] = []
    actions: list[CorrectiveAction] = []
    notes: list[str] = []
    n_attempts = 0

    def _hit_max_attempts() -> bool:
        nonlocal n_attempts
        if n_attempts >= max_attempts:
            notes.append(f"Limite max_attempts={max_attempts} atteinte ; analyse partielle.")
            return True
        return False

    # 1. Tester chaque periode d'indisponibilite
    for spec_idx, spec in enumerate(instance.machine_unavailability):
        if _hit_max_attempts():
            break
        for period_idx, period in enumerate(spec.periods):
            if _hit_max_attempts():
                break
            n_attempts += 1
            modified = _remove_unavailability_period(instance, spec_idx, period_idx)
            try_result = solver.solve(modified)
            if try_result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
                identifier = f"machine_{spec.machine_id}_period_{period_idx}"
                el = MISElement(
                    kind=MISElementKind.MACHINE_UNAVAILABILITY,
                    identifier=identifier,
                    description=(
                        f"Indisponibilite [{period[0]}, {period[1]}] sur la machine "
                        f"{spec.machine_id}"
                    ),
                )
                elements.append(el)
                actions.append(
                    CorrectiveAction(
                        target_kind=el.kind,
                        target_identifier=identifier,
                        action_kind="remove_unavailability",
                        description=(
                            f"Retirer ou reduire la plage d'indisponibilite "
                            f"[{period[0]}, {period[1]}] sur la machine {spec.machine_id}."
                        ),
                    )
                )

    # 2. Tester chaque job
    for job_idx, job in enumerate(instance.jobs):
        if _hit_max_attempts():
            break
        n_attempts += 1
        modified = _remove_job(instance, job_idx)
        if not modified.jobs:
            # Inutile de tester l'instance vide.
            continue
        try_result = solver.solve(modified)
        if try_result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            identifier = f"job_{job.job_id}"
            extra = []
            if job.deadline is not None:
                extra.append(f"deadline {job.deadline}")
            if job.client is not None:
                extra.append(f"client {job.client}")
            extras_str = " ({})".format(", ".join(extra)) if extra else ""
            el = MISElement(
                kind=MISElementKind.JOB,
                identifier=identifier,
                description=f"Job {job.job_id} avec {len(job.operations)} ops{extras_str}",
            )
            elements.append(el)
            actions.append(
                CorrectiveAction(
                    target_kind=el.kind,
                    target_identifier=identifier,
                    action_kind="defer_job",
                    description=f"Reporter ou retirer le job {job.job_id}{extras_str}.",
                )
            )

    # 3. Tester chaque ressource partagee
    for sr_idx, sr in enumerate(instance.shared_resources):
        if _hit_max_attempts():
            break
        n_attempts += 1
        modified = _remove_shared_resource(instance, sr_idx)
        try_result = solver.solve(modified)
        if try_result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            identifier = f"shared_resource_{sr.resource_name}"
            el = MISElement(
                kind=MISElementKind.SHARED_RESOURCE,
                identifier=identifier,
                description=(
                    f"Ressource partagee '{sr.resource_name}' "
                    f"(machines {sr.machine_ids}, capacite {sr.max_concurrent})"
                ),
            )
            elements.append(el)
            actions.append(
                CorrectiveAction(
                    target_kind=el.kind,
                    target_identifier=identifier,
                    action_kind="increase_capacity",
                    description=(
                        f"Augmenter la capacite de la ressource '{sr.resource_name}' "
                        f"(actuellement {sr.max_concurrent})."
                    ),
                )
            )

    if not elements:
        notes.append(
            "Aucun element singleton n'a ete identifie comme cause unique. "
            "L'infaisabilite est probablement combinatoire (interaction de plusieurs "
            "contraintes). V2 : extraction par paires."
        )

    return MISReport(
        initial_status=SolverStatus.INFEASIBLE,
        elements=elements,
        suggested_actions=actions,
        n_attempts=n_attempts,
        notes=notes,
    )


def default_mis_extractor(instance: WorkshopInstance) -> str:
    """Extracteur MIS par defaut, signature compatible avec
    `solve_with_circuit_breaker(mis_extractor=...)` de Phase 2.4.

    Retourne le `to_summary()` du `MISReport` (texte exploitable). Pour un
    rendering NL plus riche, instancier `ExplanationAgent` (3.7) et lui passer
    le `MISReport.model_dump()`.
    """
    report = extract_mis_approximate(instance)
    return report.to_summary()


__all__ = [
    "CorrectiveAction",
    "MISElement",
    "MISElementKind",
    "MISReport",
    "default_mis_extractor",
    "extract_mis_approximate",
]
